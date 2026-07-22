"""Phase 5 daily housekeeping job (plan 5.1-5.3): follow-up task creation,
is_stale flag maintenance, and making the Phase 2 lazy notification checks
independent of who happens to open the app.

Multi-instance note (audit JV-9): `entrypoint.sh` already runs
`--workers 2` in production -- each worker is a separate OS process that
would start its own copy of this scheduler, and both would fire the job at
the same time. Rather than trying to prevent that at the scheduling layer,
`run_daily_housekeeping()` wraps its work in a Postgres advisory lock: every
worker's scheduler calls it, but only the one that acquires the lock does
anything -- the rest no-op immediately. This also covers the same risk from
--reload in dev spawning an extra process.
"""
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text
from database import SessionLocal
from models import Project, Deal, Activity, EventLog, User
from utils import log_event
from thresholds import get_thresholds, business_days_since

# Arbitrary fixed key for pg_try_advisory_lock/pg_advisory_unlock -- must be
# the same constant every time this job runs, and shouldn't collide with any
# other advisory lock this codebase might use in the future (none currently
# do). Postgres advisory locks take a bigint; any fixed value works.
ADVISORY_LOCK_KEY = 5_190_001


def run_daily_housekeeping():
    """Entry point for both the scheduled job and the admin manual-trigger
    endpoint (routers/settings_router.py) -- same function either way, so
    there's no separate "test-only" code path to drift from the real one.
    Opens its own session (like server.py::seed()) since it runs outside
    any request context.
    """
    db = SessionLocal()
    acquired = False
    try:
        acquired = bool(db.execute(text("SELECT pg_try_advisory_lock(:key)"),
                                   {"key": ADVISORY_LOCK_KEY}).scalar())
        if not acquired:
            return {"ran": False, "reason": "another worker is already running this job"}
        now = datetime.now(timezone.utc)
        result = {"ran": True}
        result.update(_run_follow_up_tasks(db, now))
        result.update(_run_stale_flags(db, now))
        result.update(_run_notification_sync(db))
        db.commit()
        return result
    finally:
        if acquired:
            db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": ADVISORY_LOCK_KEY})
        db.close()


def _run_follow_up_tasks(db, now) -> dict:
    """Plan 5.2: a completed project whose closed_at + follow_up_days has
    elapsed gets a follow-up check-in Activity for its owner, exactly once.
    Idempotency marker: an EventLog(entity_type="project", event_type=
    "follow_up_task_created") row -- its activity_id also lets
    routers/projects.py::complete_follow_up find "the" pending task later,
    so this is the one place that marker gets created."""
    already_done = {
        eid for (eid,) in db.query(EventLog.entity_id)
        .filter(EventLog.entity_type == "project", EventLog.event_type == "follow_up_task_created").all()
    }
    candidates = db.query(Project).filter(Project.status == "completed", Project.closed_at.isnot(None)).all()
    created = 0
    for p in candidates:
        if p.id in already_done:
            continue
        due = p.closed_at + timedelta(days=p.follow_up_days or 0)
        if due > now:
            continue
        a = Activity(type="task", subject=f"Follow-up check-in: {p.name}",
                    description="Plan 5.2 automated follow-up -- record satisfaction and any referral.",
                    due_date=now, project_id=p.id, company_id=p.company_id, contact_id=p.contact_id,
                    owner_id=p.owner_id)
        db.add(a)
        db.flush()
        log_event(db, "project", p.id, "follow_up_task_created", actor=None, actor_type="service",
                 activity_id=a.id)
        created += 1
    return {"follow_up_tasks_created": created}


def _run_stale_flags(db, now) -> dict:
    """Plan 5.3: is_stale is a stored, job-maintained flag -- never touches
    stage. True when ball_in_court='us' has sat past the D7 stale_days
    threshold; false otherwise (including whenever ball_in_court isn't 'us'
    at all), so it's cleared automatically once the deal moves on."""
    stale_days = get_thresholds(db)["stale_days"]
    changed = 0
    for d in db.query(Deal).all():
        should_be_stale = bool(
            d.ball_in_court == "us" and d.last_contact_at is not None
            and business_days_since(d.last_contact_at, now) >= stale_days
        )
        if should_be_stale != d.is_stale:
            log_event(db, "deal", d.id, "stale_flag_changed", actor=None, actor_type="service",
                     from_value=str(d.is_stale), to_value=str(should_be_stale))
            d.is_stale = should_be_stale
            changed += 1
    return {"deals_stale_flag_changed": changed}


def _run_notification_sync(db) -> dict:
    """Plan 5.3: the Phase 2 lazy auto_unclaimed_lead/auto_awaiting_response
    checks only ever ran when a user happened to call GET /notifications --
    reuse the exact same _sync() (no duplicated logic) for every active user
    so they don't depend on who opens the app that day."""
    from routers.notifications import _sync
    users = db.query(User).filter(User.active == True).all()
    for u in users:
        _sync(db, u)
    return {"users_notifications_synced": len(users)}


def start_scheduler():
    """Called once from server.py's startup hook. Each worker process gets
    its own BackgroundScheduler + thread; the advisory lock in
    run_daily_housekeeping() is what actually prevents duplicate work, not
    this function -- see the module docstring."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_daily_housekeeping, "cron", hour=2, minute=0, id="daily_housekeeping")
    scheduler.start()
    return scheduler
