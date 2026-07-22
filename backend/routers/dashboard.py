from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Contact, Company, Deal, Project, Milestone, Activity, User
from auth import get_current_user
from visibility import visibility_filter
from financials import can_view_financials, zero_by_currency, add_currency
from utils import resolved_milestone_amount

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", summary="Get dashboard KPIs",
           description="Aggregate counts/sums across all contacts, companies, deals, projects, and open tasks, plus breakdowns by deal stage, contact status, and project status. All deal/project figures are visibility-scoped (private ones the caller can't see are excluded); contacts/companies/activities are not visibility-scoped. pipeline_value/won_value/deals_by_stage[].value_by_currency/cash_flow_by_currency are broken out per currency (plan 4.2: never summed across HUF/EUR), and null without view_financials (this doesn't bypass the schema layer like *Out does, so it's masked explicitly here). cash_flow_by_currency (4.4) is invoiced-but-not-yet-paid milestone amounts, request-time computed (no Invoice table).")
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    deal_vis = visibility_filter(db, Deal, "deal", user)
    project_vis = visibility_filter(db, Project, "project", user)

    total_contacts = db.query(func.count(Contact.id)).scalar()
    total_companies = db.query(func.count(Company.id)).scalar()
    active_projects = db.query(func.count(Project.id)).filter(
        Project.status == "active", project_vis).scalar()
    open_deals = db.query(func.count(Deal.id)).filter(
        ~Deal.stage.in_(["won", "lost"]), deal_vis).scalar()

    can_see_money = can_view_financials(db, user)

    def sum_by_currency(*filters) -> dict:
        rows = db.query(Deal.currency, func.coalesce(func.sum(Deal.value), 0)) \
            .filter(*filters).group_by(Deal.currency).all()
        out = zero_by_currency()
        out.update({cur: float(v) for cur, v in rows if cur in out})
        return out

    pipeline_value = sum_by_currency(~Deal.stage.in_(["won", "lost"]), deal_vis)
    won_value = sum_by_currency(Deal.stage == "won", deal_vis)

    # deals by stage, each broken out per currency
    stage_rows = db.query(Deal.stage, Deal.currency, func.count(Deal.id), func.coalesce(func.sum(Deal.value), 0)) \
        .filter(deal_vis).group_by(Deal.stage, Deal.currency).all()
    by_stage = {}
    for stage, currency, count, value in stage_rows:
        row = by_stage.setdefault(stage, {"stage": stage, "count": 0, "value_by_currency": zero_by_currency()})
        row["count"] += count
        add_currency(row["value_by_currency"], currency, float(value))
    deals_by_stage = list(by_stage.values())
    if not can_see_money:
        for row in deals_by_stage:
            row["value_by_currency"] = None

    # contacts by status
    status_rows = db.query(Contact.status, func.count(Contact.id)).group_by(Contact.status).all()
    contacts_by_status = [{"status": s, "count": c} for s, c in status_rows]

    # projects by status
    proj_rows = db.query(Project.status, func.count(Project.id)).filter(project_vis) \
        .group_by(Project.status).all()
    projects_by_status = [{"status": s, "count": c} for s, c in proj_rows]

    open_tasks = db.query(func.count(Activity.id)).filter(Activity.completed == False).scalar()

    # 4.4: cash-flow -- invoiced-but-not-yet-paid milestones, summed per
    # currency. Request-time computed (no Invoice table); a percentage
    # milestone resolves via resolved_milestone_amount (percentage of its
    # own project's budget), same helper the milestones router uses for its
    # budget-mismatch warning.
    cash_flow = zero_by_currency()
    if can_see_money:
        rows = db.query(Milestone, Project).join(Project, Milestone.project_id == Project.id) \
            .filter(Milestone.payment_status == "invoiced", project_vis).all()
        for m, p in rows:
            add_currency(cash_flow, p.currency, resolved_milestone_amount(m, p))

    return {
        "total_contacts": total_contacts,
        "total_companies": total_companies,
        "active_projects": active_projects,
        "open_deals": open_deals,
        "pipeline_value": pipeline_value if can_see_money else None,
        "won_value": won_value if can_see_money else None,
        "open_tasks": open_tasks,
        "deals_by_stage": deals_by_stage,
        "contacts_by_status": contacts_by_status,
        "projects_by_status": projects_by_status,
        "cash_flow_by_currency": cash_flow if can_see_money else None,
    }
