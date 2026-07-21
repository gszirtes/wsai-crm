from sqlalchemy import func
from sqlalchemy.orm import Session
from models import TimeEntry, EventLog, AppSetting


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


def log_event(db: Session, entity_type: str, entity_id: str, event_type: str, actor,
              actor_type: str = "user", from_value: str = None, to_value: str = None,
              activity_id: str = None, note: str = None) -> EventLog:
    """Append one row to the EventLog audit trail.

    `actor` is whatever principal performed the write — a `User` in every
    caller today, but the field is duck-typed (just needs `.id`) so a future
    ServiceAccount principal (Phase 1/6) can be passed with actor_type="service"
    without changing this helper. Only adds to the session; the caller's own
    db.commit() persists it alongside the actual entity write, so a write and
    its audit row always land in the same transaction.
    """
    ev = EventLog(
        entity_type=entity_type, entity_id=entity_id, event_type=event_type,
        from_value=from_value, to_value=to_value,
        actor_type=actor_type, actor_id=actor.id if actor is not None else None,
        activity_id=activity_id, note=note,
    )
    db.add(ev)
    return ev
