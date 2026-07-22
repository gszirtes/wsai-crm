from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Notification, Activity, Project, Deal, User
from auth import get_current_user
from utils import logged_hours_for
from capabilities import has_capability
from thresholds import get_thresholds, business_days_since
from visibility import visibility_filter

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
        over = p.estimated_hours and logged_hours_for(db, p.id) > p.estimated_hours
        late = p.end_date and (p.end_date.replace(tzinfo=timezone.utc) if p.end_date.tzinfo is None else p.end_date) < now
        if over or late:
            desired[f"project_risk:{p.id}"] = {
                "type": "auto_project_risk",
                "title": "Project needs attention",
                "body": f"{p.name} is {'over budget' if over else 'past its deadline'}",
                "link": f"/projects/{p.id}",
            }

    # D1/JV-10: an unowned lead isn't anyone's (owner_id IS NULL, so the
    # owner_id==user.id lazy pattern above would never surface it to anyone)
    # -- surfaced instead to whoever has view_all_reports (managers/admin),
    # not tied to a specific assignee. view_all_reports is admin-configurable
    # and could in principle be granted to a non-admin/manager role, so this
    # still applies the same visibility_filter list_deals(unassigned=true)
    # uses -- a private unassigned deal must not leak its title/existence to
    # a view_all_reports-holder who isn't a member of it.
    if has_capability(db, user.role, "view_all_reports"):
        threshold_days = get_thresholds(db)["unassigned_days"]
        unclaimed = db.query(Deal).filter(Deal.owner_id.is_(None),
                                          visibility_filter(db, Deal, "deal", user)).all()
        for d in unclaimed:
            if business_days_since(d.created_at, now) >= threshold_days:
                desired[f"unclaimed_lead:{d.id}"] = {
                    "type": "auto_unclaimed_lead",
                    "title": "Unclaimed lead",
                    "body": d.title,
                    "link": f"/deals/{d.id}",
                }

    # 2.2/D7: the ball has been in our court too long -- surfaced to the
    # deal's own owner, same lazy owner_id==user.id pattern as tasks/projects.
    awaiting_days = get_thresholds(db)["awaiting_response_days"]
    awaiting = db.query(Deal).filter(Deal.owner_id == user.id, Deal.ball_in_court == "us",
                                     Deal.last_contact_at != None).all()
    for d in awaiting:
        if business_days_since(d.last_contact_at, now) >= awaiting_days:
            desired[f"awaiting_response:{d.id}"] = {
                "type": "auto_awaiting_response",
                "title": "Awaiting your response",
                "body": d.title,
                "link": f"/deals/{d.id}",
            }
    return desired


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


@router.get("", summary="List notifications", description="Sync auto-generated notifications (overdue/due-today tasks, at-risk projects) for the current user, then list them, unread first.")
def list_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _sync(db, user)
    items = db.query(Notification).filter(Notification.user_id == user.id) \
        .order_by(Notification.read.asc(), Notification.created_at.desc()).all()
    return {
        "items": [{"id": n.id, "type": n.type, "title": n.title, "body": n.body,
                   "link": n.link, "read": n.read, "created_at": n.created_at} for n in items],
        "unread": sum(1 for n in items if not n.read),
    }


@router.post("/{notification_id}/read", summary="Mark one notification read", description="Mark a single notification (owned by the current user) as read.")
def mark_read(notification_id: str, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    n = db.query(Notification).filter(Notification.id == notification_id,
                                      Notification.user_id == user.id).first()
    if not n:
        raise HTTPException(status_code=404, detail="Not found")
    n.read = True
    db.commit()
    return {"success": True}


@router.post("/read-all", summary="Mark all notifications read", description="Mark all of the current user's unread notifications as read.")
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(Notification).filter(Notification.user_id == user.id, Notification.read == False) \
        .update({Notification.read: True})
    db.commit()
    return {"success": True}
