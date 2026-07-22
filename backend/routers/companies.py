from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Company, Contact, Deal, Project, Activity, User
from schemas import CompanyCreate, CompanyOut, ContactOut, DealOut, ProjectOut
from auth import get_current_user, require_write
from utils import log_event, owner_id_for
from visibility import visibility_filter
from financials import mask_deal_out, mask_project_out, can_view_financials

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("", response_model=list[CompanyOut],
           summary="List companies", description="List companies, optionally filtered by a case-insensitive name search, newest first.")
def list_companies(search: str = "", db: Session = Depends(get_db),
                   _: User = Depends(get_current_user)):
    q = db.query(Company)
    if search:
        q = q.filter(Company.name.ilike(f"%{search}%"))
    return q.order_by(Company.created_at.desc()).all()


@router.get("/{company_id}/detail",
           summary="Get company with related records", description="Company plus its contacts, deals, and projects. The deals/projects lists are visibility-filtered (private ones only show for admin/manager/owner/member) and their money fields masked without view_financials -- the company record itself is not visibility- or financially-scoped.")
def company_detail(company_id: str, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    c = db.query(Company).filter(Company.id == company_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    contacts = db.query(Contact).filter(Contact.company_id == company_id).all()
    deals = db.query(Deal).filter(Deal.company_id == company_id, visibility_filter(db, Deal, "deal", user)).all()
    projects = db.query(Project).filter(Project.company_id == company_id,
                                        visibility_filter(db, Project, "project", user)).all()
    can_view = can_view_financials(db, user)
    return {
        "company": CompanyOut.model_validate(c).model_dump(),
        "contacts": [ContactOut.model_validate(x).model_dump() for x in contacts],
        "deals": [mask_deal_out(db, user, DealOut.model_validate(x), can_view).model_dump() for x in deals],
        "projects": [mask_project_out(db, user, ProjectOut.model_validate(x), can_view).model_dump() for x in projects],
    }


@router.get("/{company_id}", response_model=CompanyOut,
           summary="Get a company", description="Get a single company by id.")
def get_company(company_id: str, db: Session = Depends(get_db),
                _: User = Depends(get_current_user)):
    c = db.query(Company).filter(Company.id == company_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    return c


@router.post("", response_model=CompanyOut,
            summary="Create a company", description="owner_id is always set server-side to the creating user, never accepted from the payload.")
def create_company(payload: CompanyCreate, db: Session = Depends(get_db),
                   user: User = Depends(require_write)):
    c = Company(**payload.model_dump(), owner_id=owner_id_for(user))
    db.add(c)
    db.flush()
    log_event(db, "company", c.id, "created", user)
    db.commit()
    db.refresh(c)
    return c


@router.put("/{company_id}", response_model=CompanyOut,
           summary="Update a company", description="Full replace of the editable fields (owner_id is preserved, not part of the payload).")
def update_company(company_id: str, payload: CompanyCreate, db: Session = Depends(get_db),
                   user: User = Depends(require_write)):
    c = db.query(Company).filter(Company.id == company_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    for k, v in payload.model_dump().items():
        setattr(c, k, v)
    # Company has no single stage/status field to diff (unlike Deal/Contact/
    # Project), so this is a generic "updated" event rather than a
    # conditional stage_changed/status_changed one.
    log_event(db, "company", c.id, "updated", user)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/{company_id}",
              summary="Delete a company", description="Hard delete; nulls out company_id on any contacts/deals/projects/activities that referenced it first. Logs a deleted event.")
def delete_company(company_id: str, db: Session = Depends(get_db),
                   user: User = Depends(require_write)):
    c = db.query(Company).filter(Company.id == company_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    # Null out child references before deleting
    db.query(Contact).filter(Contact.company_id == company_id).update({Contact.company_id: None})
    db.query(Deal).filter(Deal.company_id == company_id).update({Deal.company_id: None})
    db.query(Deal).filter(Deal.contract_company_id == company_id).update({Deal.contract_company_id: None})
    db.query(Project).filter(Project.company_id == company_id).update({Project.company_id: None})
    db.query(Activity).filter(Activity.company_id == company_id).update({Activity.company_id: None})
    log_event(db, "company", c.id, "deleted", user)
    db.delete(c)
    db.commit()
    return {"success": True}
