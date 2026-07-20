from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Contact, Company, Deal, Project, Activity, User
from auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", summary="Get dashboard KPIs",
           description="Aggregate counts/sums across all contacts, companies, deals, projects, and open tasks, plus breakdowns by deal stage, contact status, and project status.")
def stats(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    total_contacts = db.query(func.count(Contact.id)).scalar()
    total_companies = db.query(func.count(Company.id)).scalar()
    active_projects = db.query(func.count(Project.id)).filter(Project.status == "active").scalar()
    open_deals = db.query(func.count(Deal.id)).filter(~Deal.stage.in_(["won", "lost"])).scalar()

    pipeline_value = db.query(func.coalesce(func.sum(Deal.value), 0)).filter(
        ~Deal.stage.in_(["won", "lost"])).scalar()
    won_value = db.query(func.coalesce(func.sum(Deal.value), 0)).filter(
        Deal.stage == "won").scalar()

    # deals by stage
    stage_rows = db.query(Deal.stage, func.count(Deal.id), func.coalesce(func.sum(Deal.value), 0)) \
        .group_by(Deal.stage).all()
    deals_by_stage = [{"stage": s, "count": c, "value": float(v)} for s, c, v in stage_rows]

    # contacts by status
    status_rows = db.query(Contact.status, func.count(Contact.id)).group_by(Contact.status).all()
    contacts_by_status = [{"status": s, "count": c} for s, c in status_rows]

    # projects by status
    proj_rows = db.query(Project.status, func.count(Project.id)).group_by(Project.status).all()
    projects_by_status = [{"status": s, "count": c} for s, c in proj_rows]

    open_tasks = db.query(func.count(Activity.id)).filter(Activity.completed == False).scalar()

    return {
        "total_contacts": total_contacts,
        "total_companies": total_companies,
        "active_projects": active_projects,
        "open_deals": open_deals,
        "pipeline_value": float(pipeline_value),
        "won_value": float(won_value),
        "open_tasks": open_tasks,
        "deals_by_stage": deals_by_stage,
        "contacts_by_status": contacts_by_status,
        "projects_by_status": projects_by_status,
    }
