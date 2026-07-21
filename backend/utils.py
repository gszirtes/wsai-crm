from sqlalchemy import func
from sqlalchemy.orm import Session
from models import TimeEntry, EventLog, AppSetting, ServiceAccount


def logged_hours_for(db: Session, project_id: str) -> float:
    """Total hours logged for a project across all time entries."""
    return float(db.query(func.coalesce(func.sum(TimeEntry.hours), 0))
                 .filter(TimeEntry.project_id == project_id).scalar())


def get_setting(db: Session, key: str):
    """Generic AppSetting key-value read. Shared by ai_service.py (OpenRouter
    key/model) and capabilities.py (role_capabilities matrix) -- one accessor
    for the one key-value table, rather than each caller rolling its own."""
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return row.value if row else None


def set_setting(db: Session, key: str, value: str):
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    db.commit()


def owner_id_for(actor) -> str:
    """FK-safe owner/user id for a write. `owner_id` (Company/Contact/Deal/
    Project/Activity) and `user_id` (TimeEntry/Notification/AICommandLog) are
    all FKs to `users.id` specifically -- a ServiceAccount lives in a
    different table with its own id space, so `service_account.id` would
    violate that FK outright (a real bug this helper exists to prevent, not
    a hypothetical one: it was caught by test_service_account_write_logs_
    service_actor failing with a ForeignKeyViolation during Phase 1).
    A service-authenticated write leaves the entity unassigned/ownerless
    (None) rather than erroring -- consistent with owner_id already being
    nullable everywhere it's used.
    """
    return None if isinstance(actor, ServiceAccount) else actor.id


def log_event(db: Session, entity_type: str, entity_id: str, event_type: str, actor,
              actor_type: str = None, from_value: str = None, to_value: str = None,
              activity_id: str = None, note: str = None) -> EventLog:
    """Append one row to the EventLog audit trail.

    `actor` is whatever principal performed the write — a `User` or (Phase 1)
    a `ServiceAccount`. `actor_type` is auto-inferred from `actor`'s type when
    not passed explicitly, so none of the ~30 existing log_event() call sites
    across the routers needed to change when ServiceAccount was introduced --
    they all just pass whatever `get_current_user()` gave them and get the
    right actor_type for free. Only adds to the session; the caller's own
    db.commit() persists it alongside the actual entity write, so a write and
    its audit row always land in the same transaction.
    """
    if actor_type is None:
        actor_type = "service" if isinstance(actor, ServiceAccount) else "user"
    ev = EventLog(
        entity_type=entity_type, entity_id=entity_id, event_type=event_type,
        from_value=from_value, to_value=to_value,
        actor_type=actor_type, actor_id=actor.id if actor is not None else None,
        activity_id=activity_id, note=note,
    )
    db.add(ev)
    return ev
