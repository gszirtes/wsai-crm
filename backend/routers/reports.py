from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import TimeEntry, Project, Deal, EventLog, User
from auth import require_capability, get_current_user
from financials import can_view_financials

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def period_start(period: str) -> datetime:
    now = datetime.now(timezone.utc)
    if period == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # default: this week (Monday)
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/utilization", summary="Get team utilization report",
           description="Per-user total/billable hours, billable amount, and utilization % for the current week or month. Requires view_all_reports (this shows everyone's hours, not just the caller's own). billable_amount figures are null without view_financials -- a user could in principle have view_all_reports but not view_financials, so this is checked independently.")
def utilization(period: str = "week", db: Session = Depends(get_db),
                user: User = Depends(require_capability("view_all_reports"))):
    can_see_money = can_view_financials(db, user)
    start = period_start(period)
    entries = db.query(TimeEntry).filter(TimeEntry.entry_date >= start).all()
    rates = {p.id: (p.hourly_rate or 0) for p in db.query(Project).all()}

    agg = {}
    for e in entries:
        a = agg.setdefault(e.user_id, {"total": 0.0, "billable": 0.0, "amount": 0.0})
        a["total"] += e.hours or 0
        if e.billable:
            a["billable"] += e.hours or 0
            a["amount"] += (e.hours or 0) * rates.get(e.project_id, 0)

    rows = []
    for u in db.query(User).filter(User.active == True, User.role != "guest").all():
        a = agg.get(u.id, {"total": 0.0, "billable": 0.0, "amount": 0.0})
        rows.append({
            "user_id": u.id, "name": u.name, "role": u.role,
            "total_hours": round(a["total"], 2),
            "billable_hours": round(a["billable"], 2),
            "billable_amount": round(a["amount"], 2) if can_see_money else None,
            "utilization_pct": round((a["billable"] / a["total"] * 100) if a["total"] else 0, 0),
        })
    rows.sort(key=lambda r: r["billable_hours"], reverse=True)

    return {
        "period": period,
        "period_start": start.isoformat(),
        "totals": {
            "total_hours": round(sum(r["total_hours"] for r in rows), 2),
            "billable_hours": round(sum(r["billable_hours"] for r in rows), 2),
            "billable_amount": round(sum(a.get("amount", 0) for a in agg.values()), 2) if can_see_money else None,
        },
        "users": rows,
    }


@router.get("/deal-flow", summary="Get deal-flow report",
           description="2.3: won/lost ratio, average pass count (ball_in_court direction changes, D4) to won deals, and average days spent per stage -- reconstructed from the EventLog stage_changed history, same as utilization not visibility-scoped (view_all_reports implies org-wide reporting). Requires view_all_reports.")
def deal_flow(db: Session = Depends(get_db), user: User = Depends(require_capability("view_all_reports"))):
    now = datetime.now(timezone.utc)
    deals = db.query(Deal).all()
    deal_ids = [d.id for d in deals]
    events = db.query(EventLog).filter(EventLog.entity_type == "deal", EventLog.entity_id.in_(deal_ids)) \
        .order_by(EventLog.entity_id, EventLog.created_at.asc()).all() if deal_ids else []
    events_by_deal = {}
    for e in events:
        events_by_deal.setdefault(e.entity_id, []).append(e)

    won = lost = 0
    pass_counts_to_won = []
    stage_durations_days = {}

    for d in deals:
        if d.stage == "won":
            won += 1
        elif d.stage == "lost":
            lost += 1

        deal_events = events_by_deal.get(d.id, [])
        stage_changes = [e for e in deal_events if e.event_type == "stage_changed"]
        pass_changes = [e for e in deal_events if e.event_type == "ball_in_court_changed"]

        if d.stage == "won":
            pass_counts_to_won.append(len(pass_changes))

        # Reconstruct time-in-stage from the stage_changed history: from_value
        # on the first transition is the stage the deal was created in.
        cursor_time = _aware(d.created_at)
        cursor_stage = stage_changes[0].from_value if stage_changes else d.stage
        for sc in stage_changes:
            sc_time = _aware(sc.created_at)
            stage_durations_days.setdefault(cursor_stage, []).append((sc_time - cursor_time).total_seconds() / 86400)
            cursor_time = sc_time
            cursor_stage = sc.to_value
        stage_durations_days.setdefault(cursor_stage, []).append((now - cursor_time).total_seconds() / 86400)

    avg_days_per_stage = {
        stage: round(sum(durs) / len(durs), 2)
        for stage, durs in stage_durations_days.items()
    }

    return {
        "won": won,
        "lost": lost,
        "won_lost_ratio": round(won / lost, 2) if lost else None,
        "avg_passes_to_won": round(sum(pass_counts_to_won) / len(pass_counts_to_won), 2) if pass_counts_to_won else 0,
        "avg_days_per_stage": avg_days_per_stage,
    }
