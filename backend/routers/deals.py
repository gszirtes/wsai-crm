from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Deal, Company, Contact, Activity, User
from schemas import DealCreate, DealOut, StageUpdate, ActivityOut
from auth import get_current_user, require_write

router = APIRouter(prefix="/api/deals", tags=["deals"])

STAGE_PROBABILITY = {"lead": 10, "qualified": 30, "proposal": 55,
                     "negotiation": 75, "won": 100, "lost": 0}


@router.get("", response_model=list[DealOut])
def list_deals(stage: str = "", db: Session = Depends(get_db),
               _: User = Depends(get_current_user)):
    q = db.query(Deal)
    if stage:
        q = q.filter(Deal.stage == stage)
    return q.order_by(Deal.created_at.desc()).all()


@router.get("/{deal_id}/detail")
def deal_detail(deal_id: str, db: Session = Depends(get_db),
                _: User = Depends(get_current_user)):
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Deal not found")
    company = db.query(Company).filter(Company.id == d.company_id).first() if d.company_id else None
    contact = db.query(Contact).filter(Contact.id == d.contact_id).first() if d.contact_id else None
    activities = db.query(Activity).filter(Activity.deal_id == deal_id) \
        .order_by(Activity.created_at.desc()).all()
    return {
        "deal": DealOut.model_validate(d).model_dump(),
        "company_name": company.name if company else None,
        "contact_name": f"{contact.first_name} {contact.last_name or ''}".strip() if contact else None,
        "activities": [ActivityOut.model_validate(a).model_dump() for a in activities],
    }


@router.get("/{deal_id}", response_model=DealOut)
def get_deal(deal_id: str, db: Session = Depends(get_db),
             _: User = Depends(get_current_user)):
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Deal not found")
    return d


@router.post("", response_model=DealOut)
def create_deal(payload: DealCreate, db: Session = Depends(get_db),
                user: User = Depends(require_write)):
    d = Deal(**payload.model_dump(), owner_id=user.id)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


@router.put("/{deal_id}", response_model=DealOut)
def update_deal(deal_id: str, payload: DealCreate, db: Session = Depends(get_db),
                user: User = Depends(require_write)):
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Deal not found")
    for k, v in payload.model_dump().items():
        setattr(d, k, v)
    db.commit()
    db.refresh(d)
    return d


@router.patch("/{deal_id}/stage", response_model=DealOut)
def update_stage(deal_id: str, payload: StageUpdate, db: Session = Depends(get_db),
                 user: User = Depends(require_write)):
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Deal not found")
    d.stage = payload.stage
    d.probability = STAGE_PROBABILITY.get(payload.stage, d.probability)
    db.commit()
    db.refresh(d)
    return d


@router.delete("/{deal_id}")
def delete_deal(deal_id: str, db: Session = Depends(get_db),
                user: User = Depends(require_write)):
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Deal not found")
    # Null out child references before deleting
    db.query(Activity).filter(Activity.deal_id == deal_id).update({Activity.deal_id: None})
    db.delete(d)
    db.commit()
    return {"success": True}
