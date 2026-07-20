from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Activity, User
from schemas import ActivityCreate, ActivityOut
from auth import get_current_user, require_write
from utils import log_event

router = APIRouter(prefix="/api/activities", tags=["activities"])

_PARENT_LINKS = (("contact", "contact_id"), ("company", "company_id"),
                 ("deal", "deal_id"), ("project", "project_id"))


def _log_activity_created(db: Session, a: Activity, user):
    log_event(db, "activity", a.id, "created", user)
    for entity_type, field in _PARENT_LINKS:
        parent_id = getattr(a, field)
        if parent_id:
            log_event(db, entity_type, parent_id, "activity_logged", user,
                      activity_id=a.id, note=a.subject)


@router.get("", response_model=list[ActivityOut],
           summary="List activities", description="List activities, optionally filtered by completed/contact/deal/project, or sorted by soonest due date (upcoming=true).")
def list_activities(completed: str = "", contact_id: str = "", deal_id: str = "",
                    project_id: str = "", upcoming: str = "",
                    db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    q = db.query(Activity)
    if completed in ("true", "false"):
        q = q.filter(Activity.completed == (completed == "true"))
    if contact_id:
        q = q.filter(Activity.contact_id == contact_id)
    if deal_id:
        q = q.filter(Activity.deal_id == deal_id)
    if project_id:
        q = q.filter(Activity.project_id == project_id)
    order = Activity.due_date.asc().nullslast() if upcoming == "true" else Activity.created_at.desc()
    return q.order_by(order).all()


@router.post("", response_model=ActivityOut,
            summary="Create an activity", description="owner_id is always set server-side to the creating user. Logs a created event, plus an activity_logged event on every linked contact/company/deal/project.")
def create_activity(payload: ActivityCreate, db: Session = Depends(get_db),
                    user: User = Depends(require_write)):
    a = Activity(**payload.model_dump(), owner_id=user.id)
    db.add(a)
    db.flush()
    _log_activity_created(db, a, user)
    db.commit()
    db.refresh(a)
    return a


@router.put("/{activity_id}", response_model=ActivityOut,
           summary="Update an activity", description="Full replace of the editable fields. Logs a status_changed event if completed differs from before (same as PATCH /toggle).")
def update_activity(activity_id: str, payload: ActivityCreate, db: Session = Depends(get_db),
                    user: User = Depends(require_write)):
    a = db.query(Activity).filter(Activity.id == activity_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Activity not found")
    old_completed = a.completed
    for k, v in payload.model_dump().items():
        setattr(a, k, v)
    if a.completed != old_completed:
        log_event(db, "activity", a.id, "status_changed", user,
                  from_value=str(old_completed), to_value=str(a.completed))
    db.commit()
    db.refresh(a)
    return a


@router.patch("/{activity_id}/toggle", response_model=ActivityOut,
             summary="Toggle completed", description="Flip an activity's completed flag. Logs a status_changed event.")
def toggle_activity(activity_id: str, db: Session = Depends(get_db),
                    user: User = Depends(require_write)):
    a = db.query(Activity).filter(Activity.id == activity_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Activity not found")
    old_completed = a.completed
    a.completed = not a.completed
    log_event(db, "activity", a.id, "status_changed", user,
              from_value=str(old_completed), to_value=str(a.completed))
    db.commit()
    db.refresh(a)
    return a


@router.delete("/{activity_id}", summary="Delete an activity", description="Hard delete. Logs a deleted event.")
def delete_activity(activity_id: str, db: Session = Depends(get_db),
                    user: User = Depends(require_write)):
    a = db.query(Activity).filter(Activity.id == activity_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Activity not found")
    log_event(db, "activity", a.id, "deleted", user)
    db.delete(a)
    db.commit()
    return {"success": True}
