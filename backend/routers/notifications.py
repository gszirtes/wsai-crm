from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Notification, Activity, Project, User
from auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _build_desired(db: Session, user: User) -> dict:
    """Compute the set of auto-notifications relevant to this user right now."""
    now = datetime.now(timezone.utc)
    today = now.date()
    desired = {}

    tasks = db.query(Activity).filter(
        Activity.owner_id == user.id,
        Activity.completed == False,
        Activity.due_date != None,
    ).all()
    for a in tasks:
        due = a.due_date
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        if due < now and due.date() < today:
            desired[f"overdue:{a.id}"] = {
                "type": "auto_overdue",
                "title": "Overdue task",
                "body": a.subject,
                "link": "/activities",
            }
        elif due.date() == today:
            desired[f"due_today:{a.id}"] = {
                "type": "auto_due_today",
                "title": "Task due today",
                "body": a.subject,
                "link": "/activities",
            }

    projects = db.query(Project).filter(Project.owner_id == user.id).all()
    for p in projects:
        if p.status in ("completed", "cancelled"):
            continue
        over = p.estimated_hours and _logged(db, p.id) > p.estimated_hours
        late = p.end_date and (p.end_date.replace(tzinfo=timezone.utc) if p.end_date.tzinfo is None else p.end_date) < now
        if over or late:
            desired[f"project_risk:{p.id}"] = {
                "type": "auto_project_risk",
                "title": "Project needs attention",
                "body": f"{p.name} is {'over budget' if over else 'past its deadline'}",
                "link": f"/projects/{p.id}",
            }
    return desired


def _logged(db: Session, project_id: str) -> float:
    from sqlalchemy import func
    from models import TimeEntry
    return float(db.query(func.coalesce(func.sum(TimeEntry.hours), 0))
                 .filter(TimeEntry.project_id == project_id).scalar())


def _sync(db: Session, user: User):
    desired = _build_desired(db, user)
    existing = {n.key: n for n in db.query(Notification).filter(Notification.user_id == user.id).all()}
    # add new
    for key, d in desired.items():
        if key not in existing:
            db.add(Notification(user_id=user.id, key=key, type=d["type"],
                                title=d["title"], body=d["body"], link=d["link"]))
    # remove resolved auto notifications
    for key, n in existing.items():
        if n.type.startswith("auto_") and key not in desired:
            db.delete(n)
    db.commit()


@router.get("")
def list_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _sync(db, user)
    items = db.query(Notification).filter(Notification.user_id == user.id) \
        .order_by(Notification.read.asc(), Notification.created_at.desc()).all()
    return {
        "items": [{"id": n.id, "type": n.type, "title": n.title, "body": n.body,
                   "link": n.link, "read": n.read, "created_at": n.created_at} for n in items],
        "unread": sum(1 for n in items if not n.read),
    }


@router.post("/{notification_id}/read")
def mark_read(notification_id: str, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    n = db.query(Notification).filter(Notification.id == notification_id,
                                      Notification.user_id == user.id).first()
    if not n:
        raise HTTPException(status_code=404, detail="Not found")
    n.read = True
    db.commit()
    return {"success": True}


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(Notification).filter(Notification.user_id == user.id, Notification.read == False) \
        .update({Notification.read: True})
    db.commit()
    return {"success": True}
