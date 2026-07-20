from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import EventLog, User
from auth import require_role

router = APIRouter(prefix="/api/event-logs", tags=["event-logs"])


@router.get(
    "",
    summary="List audit events for one entity",
    description=(
        "Raw, chronological read of the generic EventLog audit trail for a single "
        "(entity_type, entity_id) pair. This is a Phase 0 enabler so the append-only "
        "log introduced here is actually observable end-to-end; the richer, "
        "UI-facing timeline (collapsible pass-sequences, summary stats) is a later "
        "phase. Admin/manager only for now — no per-object visibility scoping exists "
        "yet (that lands in a later phase's access-control work)."
    ),
)
def list_event_logs(entity_type: str, entity_id: str, db: Session = Depends(get_db),
                    _: User = Depends(require_role("manager"))):
    rows = db.query(EventLog).filter(EventLog.entity_type == entity_type,
                                     EventLog.entity_id == entity_id) \
        .order_by(EventLog.created_at.asc()).all()
    return [{
        "id": e.id, "entity_type": e.entity_type, "entity_id": e.entity_id,
        "event_type": e.event_type, "from_value": e.from_value, "to_value": e.to_value,
        "actor_type": e.actor_type, "actor_id": e.actor_id,
        "activity_id": e.activity_id, "note": e.note, "created_at": e.created_at,
    } for e in rows]
