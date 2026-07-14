from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Contact, Company, User
from schemas import ContactCreate, ContactOut
from auth import get_current_user, require_write

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


def _to_out(c: Contact) -> ContactOut:
    out = ContactOut.model_validate(c)
    out.company_name = c.company.name if c.company else None
    return out


@router.get("", response_model=list[ContactOut])
def list_contacts(search: str = "", status: str = "", company_id: str = "",
                  db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    q = db.query(Contact)
    if search:
        like = f"%{search}%"
        q = q.filter((Contact.first_name.ilike(like)) | (Contact.last_name.ilike(like)) |
                     (Contact.email.ilike(like)))
    if status:
        q = q.filter(Contact.status == status)
    if company_id:
        q = q.filter(Contact.company_id == company_id)
    return [_to_out(c) for c in q.order_by(Contact.created_at.desc()).all()]


@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(contact_id: str, db: Session = Depends(get_db),
                _: User = Depends(get_current_user)):
    c = db.query(Contact).filter(Contact.id == contact_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    return _to_out(c)


@router.post("", response_model=ContactOut)
def create_contact(payload: ContactCreate, db: Session = Depends(get_db),
                   user: User = Depends(require_write)):
    c = Contact(**payload.model_dump(), owner_id=user.id)
    db.add(c)
    db.commit()
    db.refresh(c)
    return _to_out(c)


@router.put("/{contact_id}", response_model=ContactOut)
def update_contact(contact_id: str, payload: ContactCreate, db: Session = Depends(get_db),
                   user: User = Depends(require_write)):
    c = db.query(Contact).filter(Contact.id == contact_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    for k, v in payload.model_dump().items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return _to_out(c)


@router.delete("/{contact_id}")
def delete_contact(contact_id: str, db: Session = Depends(get_db),
                   user: User = Depends(require_write)):
    c = db.query(Contact).filter(Contact.id == contact_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(c)
    db.commit()
    return {"success": True}
