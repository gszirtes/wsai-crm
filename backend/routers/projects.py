from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Project, TimeEntry, Activity, Company, Contact, User
from schemas import (ProjectCreate, ProjectOut, TimeEntryCreate, TimeEntryOut,
                     ActivityOut)
from auth import get_current_user, require_write
from utils import logged_hours_for, log_event

router = APIRouter(prefix="/api/projects", tags=["projects"])


def compute_health(project: Project, logged: float) -> str:
    if project.status == "completed":
        return "completed"
    if project.status == "cancelled":
        return "cancelled"
    if project.estimated_hours and logged > project.estimated_hours:
        return "over_budget"
    if project.end_date:
        end = project.end_date
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if end < datetime.now(timezone.utc):
            return "at_risk"
    return "on_track"


def to_out(db: Session, p: Project) -> ProjectOut:
    logged = logged_hours_for(db, p.id)
    out = ProjectOut.model_validate(p)
    out.logged_hours = logged
    out.health = compute_health(p, logged)
    return out


@router.get("", response_model=list[ProjectOut],
           summary="List projects", description="Paginated list of projects, optionally filtered by status, newest first. Total count is in the X-Total-Count response header.")
def list_projects(response: Response, status: str = "", limit: int = 20, offset: int = 0,
                  db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    q = db.query(Project)
    if status:
        q = q.filter(Project.status == status)
    total = q.count()
    limit = max(1, min(limit, 100))
    projects = q.order_by(Project.created_at.desc()).offset(max(0, offset)).limit(limit).all()
    ids = [p.id for p in projects]
    hours = {}
    if ids:
        rows = db.query(TimeEntry.project_id, func.coalesce(func.sum(TimeEntry.hours), 0)) \
            .filter(TimeEntry.project_id.in_(ids)).group_by(TimeEntry.project_id).all()
        hours = {pid: float(h) for pid, h in rows}
    out = []
    for p in projects:
        o = ProjectOut.model_validate(p)
        o.logged_hours = hours.get(p.id, 0.0)
        o.health = compute_health(p, o.logged_hours)
        out.append(o)
    response.headers["X-Total-Count"] = str(total)
    return out


@router.get("/{project_id}", response_model=ProjectOut,
           summary="Get a project", description="Get a single project by id, including computed logged_hours and health.")
def get_project(project_id: str, db: Session = Depends(get_db),
                _: User = Depends(get_current_user)):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return to_out(db, p)


@router.get("/{project_id}/detail",
           summary="Get project with related records", description="Project plus time entries, billable amount, health, and activity timeline.")
def project_detail(project_id: str, db: Session = Depends(get_db),
                   _: User = Depends(get_current_user)):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    logged = logged_hours_for(db, p.id)
    entries = db.query(TimeEntry).filter(TimeEntry.project_id == project_id) \
        .order_by(TimeEntry.entry_date.desc()).all()
    users = {u.id: u.name for u in db.query(User).all()}
    entry_out = []
    for e in entries:
        eo = TimeEntryOut.model_validate(e)
        eo.user_name = users.get(e.user_id)
        entry_out.append(eo)
    billable = float(db.query(func.coalesce(func.sum(TimeEntry.hours), 0))
                     .filter(TimeEntry.project_id == project_id, TimeEntry.billable == True).scalar())
    activities = db.query(Activity).filter(Activity.project_id == project_id) \
        .order_by(Activity.created_at.desc()).all()
    company = db.query(Company).filter(Company.id == p.company_id).first() if p.company_id else None
    contact = db.query(Contact).filter(Contact.id == p.contact_id).first() if p.contact_id else None
    return {
        "project": to_out(db, p),
        "logged_hours": logged,
        "billable_hours": billable,
        "billable_amount": billable * (p.hourly_rate or 0),
        "health": compute_health(p, logged),
        "company_name": company.name if company else None,
        "contact_name": f"{contact.first_name} {contact.last_name or ''}".strip() if contact else None,
        "time_entries": [e.model_dump() for e in entry_out],
        "activities": [ActivityOut.model_validate(a).model_dump() for a in activities],
    }


@router.post("", response_model=ProjectOut,
            summary="Create a project", description="owner_id is always set server-side to the creating user, never accepted from the payload.")
def create_project(payload: ProjectCreate, db: Session = Depends(get_db),
                   user: User = Depends(require_write)):
    p = Project(**payload.model_dump(), owner_id=user.id)
    db.add(p)
    db.flush()
    log_event(db, "project", p.id, "created", user)
    db.commit()
    db.refresh(p)
    return to_out(db, p)


@router.put("/{project_id}", response_model=ProjectOut,
           summary="Update a project", description="Full replace of the editable fields. Logs a status_changed event if status differs from before; no other transition guard.")
def update_project(project_id: str, payload: ProjectCreate, db: Session = Depends(get_db),
                   user: User = Depends(require_write)):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    old_status = p.status
    for k, v in payload.model_dump().items():
        setattr(p, k, v)
    if p.status != old_status:
        log_event(db, "project", p.id, "status_changed", user, from_value=old_status, to_value=p.status)
    db.commit()
    db.refresh(p)
    return to_out(db, p)


@router.delete("/{project_id}",
              summary="Delete a project", description="Hard delete; also deletes all of the project's time entries. Logs a deleted event.")
def delete_project(project_id: str, db: Session = Depends(get_db),
                   user: User = Depends(require_write)):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    db.query(TimeEntry).filter(TimeEntry.project_id == project_id).delete()
    log_event(db, "project", p.id, "deleted", user)
    db.delete(p)
    db.commit()
    return {"success": True}


# ---------- Time entries ----------
@router.get("/{project_id}/time", response_model=list[TimeEntryOut],
           summary="List time entries", description="List logged time entries for a project, most recent first.")
def list_time(project_id: str, db: Session = Depends(get_db),
              _: User = Depends(get_current_user)):
    entries = db.query(TimeEntry).filter(TimeEntry.project_id == project_id) \
        .order_by(TimeEntry.entry_date.desc()).all()
    users = {u.id: u.name for u in db.query(User).all()}
    out = []
    for e in entries:
        eo = TimeEntryOut.model_validate(e)
        eo.user_name = users.get(e.user_id)
        out.append(eo)
    return out


@router.post("/{project_id}/time", response_model=TimeEntryOut,
            summary="Log time", description="Log an hours entry against a project for the current user. user_id is always the creating user, never accepted from the payload.")
def add_time(project_id: str, payload: TimeEntryCreate, db: Session = Depends(get_db),
             user: User = Depends(require_write)):
    if not db.query(Project).filter(Project.id == project_id).first():
        raise HTTPException(status_code=404, detail="Project not found")
    entry = TimeEntry(
        project_id=project_id,
        user_id=user.id,
        hours=payload.hours,
        description=payload.description,
        billable=payload.billable if payload.billable is not None else True,
        entry_date=payload.entry_date or datetime.now(timezone.utc),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    eo = TimeEntryOut.model_validate(entry)
    eo.user_name = user.name
    return eo


@router.delete("/{project_id}/time/{entry_id}",
              summary="Delete a time entry", description="Delete one time entry. Only the entry's own creator, or an admin/manager, may delete it.")
def delete_time(project_id: str, entry_id: str, db: Session = Depends(get_db),
                user: User = Depends(require_write)):
    e = db.query(TimeEntry).filter(TimeEntry.id == entry_id,
                                   TimeEntry.project_id == project_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Time entry not found")
    if e.user_id != user.id and user.role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="You can only delete your own time entries")
    db.delete(e)
    db.commit()
    return {"success": True}
