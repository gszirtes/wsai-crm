from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import get_db
from models import Project, Milestone, User
from schemas import MilestoneCreate, MilestoneOut, MilestoneStatusUpdate
from auth import get_current_user, require_capability
from utils import log_event, resolved_milestone_amount
from visibility import can_see
from financials import mask_milestone_out, can_view_financials
from rate_limit import limiter

router = APIRouter(prefix="/api/projects/{project_id}/milestones", tags=["milestones"])


def _get_project_or_404(db: Session, project_id: str, user) -> Project:
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p or not can_see(db, "project", p, user):
        raise HTTPException(status_code=404, detail="Project not found")
    return p


@router.get("", summary="List milestones", description="A project's milestones ordered by order_index, plus the summed amount and a mismatch warning against the project's budget (plan 4.1: the sum SHOULD equal budget in a fixed-price model, but this is only a warning, not enforced). amount/total_amount/budget are null without view_financials.")
def list_milestones(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = _get_project_or_404(db, project_id, user)
    rows = db.query(Milestone).filter(Milestone.project_id == project_id) \
        .order_by(Milestone.order_index.asc()).all()
    can_view = can_view_financials(db, user)
    total = sum(resolved_milestone_amount(m, p) for m in rows)
    return {
        "milestones": [mask_milestone_out(db, user, MilestoneOut.model_validate(m), can_view).model_dump() for m in rows],
        "total_amount": total if can_view else None,
        "budget": p.budget if can_view else None,
        "budget_mismatch": can_view and rows and abs(total - (p.budget or 0)) > 0.01,
    }


@router.post("", response_model=MilestoneOut,
            summary="Add a milestone", description="Requires manage_projects. amount XOR percentage must hold (D11).")
def create_milestone(project_id: str, payload: MilestoneCreate, db: Session = Depends(get_db),
                     user: User = Depends(require_capability("manage_projects"))):
    _get_project_or_404(db, project_id, user)
    m = Milestone(**payload.model_dump(), project_id=project_id)
    db.add(m)
    db.flush()
    log_event(db, "milestone", m.id, "created", user, note=project_id)
    db.commit()
    db.refresh(m)
    return mask_milestone_out(db, user, MilestoneOut.model_validate(m))


@router.put("/{milestone_id}", response_model=MilestoneOut,
           summary="Update a milestone", description="Full replace of name/order_index/due_date/amount/percentage. Requires manage_projects. Does not touch work_status/payment_status -- use PATCH .../status for those.")
def update_milestone(project_id: str, milestone_id: str, payload: MilestoneCreate,
                     db: Session = Depends(get_db),
                     user: User = Depends(require_capability("manage_projects"))):
    _get_project_or_404(db, project_id, user)
    m = db.query(Milestone).filter(Milestone.id == milestone_id, Milestone.project_id == project_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Milestone not found")
    for k, v in payload.model_dump(exclude={"work_status", "payment_status"}).items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return mask_milestone_out(db, user, MilestoneOut.model_validate(m))


@router.patch("/{milestone_id}/status", response_model=MilestoneOut,
             summary="Change a milestone's work/payment status", description="work_status (in_progress/client_review/accepted) and payment_status (not_due/invoiceable/invoiced/paid) are independently settable and reversible in either direction (plan 4.1) -- pass either or both. Requires manage_projects. Every actual change logs a status_changed event. Rate-limited (60/minute) -- this is one of the MCP server's write tools' target routes (plan 6.3).")
@limiter.limit("60/minute")
def update_milestone_status(request: Request, project_id: str, milestone_id: str, payload: MilestoneStatusUpdate,
                            db: Session = Depends(get_db),
                            user: User = Depends(require_capability("manage_projects"))):
    _get_project_or_404(db, project_id, user)
    m = db.query(Milestone).filter(Milestone.id == milestone_id, Milestone.project_id == project_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Milestone not found")
    if payload.work_status is not None and payload.work_status != m.work_status:
        log_event(db, "milestone", m.id, "status_changed", user,
                 from_value=m.work_status, to_value=payload.work_status, note="work_status")
        m.work_status = payload.work_status
    if payload.payment_status is not None and payload.payment_status != m.payment_status:
        log_event(db, "milestone", m.id, "status_changed", user,
                 from_value=m.payment_status, to_value=payload.payment_status, note="payment_status")
        m.payment_status = payload.payment_status
    db.commit()
    db.refresh(m)
    return mask_milestone_out(db, user, MilestoneOut.model_validate(m))


@router.delete("/{milestone_id}",
              summary="Delete a milestone", description="Requires manage_projects. Logs a deleted event.")
def delete_milestone(project_id: str, milestone_id: str, db: Session = Depends(get_db),
                     user: User = Depends(require_capability("manage_projects"))):
    _get_project_or_404(db, project_id, user)
    m = db.query(Milestone).filter(Milestone.id == milestone_id, Milestone.project_id == project_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Milestone not found")
    log_event(db, "milestone", m.id, "deleted", user, note=project_id)
    db.delete(m)
    db.commit()
    return {"success": True}
