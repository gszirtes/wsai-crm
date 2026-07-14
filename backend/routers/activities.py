from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Activity, User
from schemas import ActivityCreate, ActivityOut
from auth import get_current_user, require_write

router = APIRouter(prefix="/api/activities", tags=["activities"])


@router.get("", response_model=list[ActivityOut])
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


@router.post("", response_model=ActivityOut)
def create_activity(payload: ActivityCreate, db: Session = Depends(get_db),
                    user: User = Depends(require_write)):
    a = Activity(**payload.model_dump(), owner_id=user.id)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@router.put("/{activity_id}", response_model=ActivityOut)
def update_activity(activity_id: str, payload: ActivityCreate, db: Session = Depends(get_db),
                    user: User = Depends(require_write)):
    a = db.query(Activity).filter(Activity.id == activity_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Activity not found")
    for k, v in payload.model_dump().items():
        setattr(a, k, v)
    db.commit()
    db.refresh(a)
    return a


@router.patch("/{activity_id}/toggle", response_model=ActivityOut)
def toggle_activity(activity_id: str, db: Session = Depends(get_db),
                    user: User = Depends(require_write)):
    a = db.query(Activity).filter(Activity.id == activity_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Activity not found")
    a.completed = not a.completed
    db.commit()
    db.refresh(a)
    return a


@router.delete("/{activity_id}")
def delete_activity(activity_id: str, db: Session = Depends(get_db),
                    user: User = Depends(require_write)):
    a = db.query(Activity).filter(Activity.id == activity_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Activity not found")
    db.delete(a)
    db.commit()
    return {"success": True}
