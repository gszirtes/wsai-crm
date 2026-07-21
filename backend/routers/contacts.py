from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models import Contact, Company, Deal, Activity, User
from schemas import ContactCreate, ContactOut, DealOut, ActivityOut
from auth import get_current_user, require_write
from utils import log_event
from visibility import visibility_filter
from financials import mask_deal_out

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


def _to_out(c: Contact) -> ContactOut:
    out = ContactOut.model_validate(c)
    out.company_name = c.company.name if c.company else None
    return out


@router.get("", response_model=list[ContactOut],
           summary="List contacts", description="List contacts, optionally filtered by name/email search, status, or company, newest first.")
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
    return [_to_out(c) for c in q.options(joinedload(Contact.company)).order_by(Contact.created_at.desc()).all()]


@router.get("/{contact_id}/detail",
           summary="Get contact with related records", description="Contact plus its deals and activity timeline. The deals list is visibility-filtered (private ones only show for admin/manager/owner/member) -- the contact record itself is not visibility-scoped.")
def contact_detail(contact_id: str, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    c = db.query(Contact).filter(Contact.id == contact_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    deals = db.query(Deal).filter(Deal.contact_id == contact_id, visibility_filter(db, Deal, "deal", user)) \
        .order_by(Deal.created_at.desc()).all()
    activities = db.query(Activity).filter(Activity.contact_id == contact_id) \
        .order_by(Activity.created_at.desc()).all()
    return {
        "contact": _to_out(c).model_dump(),
        "deals": [mask_deal_out(db, user, DealOut.model_validate(d)).model_dump() for d in deals],
        "activities": [ActivityOut.model_validate(a).model_dump() for a in activities],
    }


@router.get("/{contact_id}", response_model=ContactOut,
           summary="Get a contact", description="Get a single contact by id.")
def get_contact(contact_id: str, db: Session = Depends(get_db),
                _: User = Depends(get_current_user)):
    c = db.query(Contact).filter(Contact.id == contact_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    return _to_out(c)


@router.post("", response_model=ContactOut,
            summary="Create a contact", description="owner_id is always set server-side to the creating user, never accepted from the payload.")
def create_contact(payload: ContactCreate, db: Session = Depends(get_db),
                   user: User = Depends(require_write)):
    c = Contact(**payload.model_dump(), owner_id=user.id)
    db.add(c)
    db.flush()
    log_event(db, "contact", c.id, "created", user)
    db.commit()
    db.refresh(c)
    return _to_out(c)


@router.put("/{contact_id}", response_model=ContactOut,
           summary="Update a contact", description="Full replace of the editable fields. Logs a status_changed event if status differs from before.")
def update_contact(contact_id: str, payload: ContactCreate, db: Session = Depends(get_db),
                   user: User = Depends(require_write)):
    c = db.query(Contact).filter(Contact.id == contact_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    old_status = c.status
    for k, v in payload.model_dump().items():
        setattr(c, k, v)
    if c.status != old_status:
        log_event(db, "contact", c.id, "status_changed", user, from_value=old_status, to_value=c.status)
    db.commit()
    db.refresh(c)
    return _to_out(c)


@router.delete("/{contact_id}",
              summary="Delete a contact", description="Hard delete; nulls out contact_id on any deals/activities that referenced it first. Logs a deleted event.")
def delete_contact(contact_id: str, db: Session = Depends(get_db),
                   user: User = Depends(require_write)):
    c = db.query(Contact).filter(Contact.id == contact_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    # Null out child references before deleting
    db.query(Deal).filter(Deal.contact_id == contact_id).update({Deal.contact_id: None})
    db.query(Activity).filter(Activity.contact_id == contact_id).update({Activity.contact_id: None})
    log_event(db, "contact", c.id, "deleted", user)
    db.delete(c)
    db.commit()
    return {"success": True}
