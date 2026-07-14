from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Company, Contact, User
from schemas import CompanyCreate, CompanyOut
from auth import get_current_user, require_write

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("", response_model=list[CompanyOut])
def list_companies(search: str = "", db: Session = Depends(get_db),
                   _: User = Depends(get_current_user)):
    q = db.query(Company)
    if search:
        q = q.filter(Company.name.ilike(f"%{search}%"))
    return q.order_by(Company.created_at.desc()).all()


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(company_id: str, db: Session = Depends(get_db),
                _: User = Depends(get_current_user)):
    c = db.query(Company).filter(Company.id == company_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    return c


@router.post("", response_model=CompanyOut)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db),
                   user: User = Depends(require_write)):
    c = Company(**payload.model_dump(), owner_id=user.id)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/{company_id}", response_model=CompanyOut)
def update_company(company_id: str, payload: CompanyCreate, db: Session = Depends(get_db),
                   user: User = Depends(require_write)):
    c = db.query(Company).filter(Company.id == company_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    for k, v in payload.model_dump().items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/{company_id}")
def delete_company(company_id: str, db: Session = Depends(get_db),
                   user: User = Depends(require_write)):
    c = db.query(Company).filter(Company.id == company_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    db.delete(c)
    db.commit()
    return {"success": True}
