from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Deal, Company, Contact, Activity, EventLog, User
from schemas import (DealCreate, DealOut, StageUpdate, VisibilityUpdate, MemberAdd,
                     ActivityOut, OwnerUpdate, BallInCourtUpdate)
from auth import get_current_user, require_capability
from utils import log_event, owner_id_for
from capabilities import get_default_visibility
from membership import add_member, remove_member, list_members
from visibility import visibility_filter, can_see
from financials import mask_deal_out, can_view_financials
from deal_rules import check_owner_required, create_project_from_won_deal

router = APIRouter(prefix="/api/deals", tags=["deals"])

STAGE_PROBABILITY = {"lead": 10, "qualified": 30, "proposal": 55,
                     "negotiation": 75, "won": 100, "lost": 0}


def _to_out(db: Session, d: Deal, user: User, can_view: bool = None) -> DealOut:
    return mask_deal_out(db, user, DealOut.model_validate(d), can_view)


@router.get("", response_model=list[DealOut],
           summary="List deals", description="List deals, optionally filtered by stage or unassigned=true (shared-inbox leads with no owner), newest first. Private deals only appear for admin/manager, their owner, or invited members. `value` is null without view_financials.")
def list_deals(stage: str = "", unassigned: bool = False, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    q = db.query(Deal).filter(visibility_filter(db, Deal, "deal", user))
    if stage:
        q = q.filter(Deal.stage == stage)
    if unassigned:
        q = q.filter(Deal.owner_id.is_(None))
    can_view = can_view_financials(db, user)
    return [_to_out(db, d, user, can_view) for d in q.order_by(Deal.created_at.desc()).all()]


@router.get("/{deal_id}/detail",
           summary="Get deal with related records", description="Deal plus its company/contact names and activity timeline. 404 (not just for nonexistent deals) if the deal is private and this user isn't admin/manager/owner/member. `value` is null without view_financials.")
def deal_detail(deal_id: str, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d or not can_see(db, "deal", d, user):
        raise HTTPException(status_code=404, detail="Deal not found")
    company = db.query(Company).filter(Company.id == d.company_id).first() if d.company_id else None
    contact = db.query(Contact).filter(Contact.id == d.contact_id).first() if d.contact_id else None
    owner = db.query(User).filter(User.id == d.owner_id).first() if d.owner_id else None
    activities = db.query(Activity).filter(Activity.deal_id == deal_id) \
        .order_by(Activity.created_at.desc()).all()
    return {
        "deal": _to_out(db, d, user).model_dump(),
        "company_name": company.name if company else None,
        "contact_name": f"{contact.first_name} {contact.last_name or ''}".strip() if contact else None,
        "owner_name": owner.name if owner else None,
        "activities": [ActivityOut.model_validate(a).model_dump() for a in activities],
    }


@router.get("/{deal_id}/timeline",
           summary="Get deal lifecycle timeline", description="2.3: this deal's EventLog rows (entity_type='deal'), chronological, each enriched with the linked Activity's direction/subject where the event has one (activity_logged events). 404 if it's private and this user isn't admin/manager/owner/member, or if the deal was hard-deleted (no dangling-id read).")
def deal_timeline(deal_id: str, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d or not can_see(db, "deal", d, user):
        raise HTTPException(status_code=404, detail="Deal not found")
    events = db.query(EventLog).filter(EventLog.entity_type == "deal", EventLog.entity_id == deal_id) \
        .order_by(EventLog.created_at.asc()).all()
    activity_ids = [e.activity_id for e in events if e.activity_id]
    activities = {a.id: a for a in db.query(Activity).filter(Activity.id.in_(activity_ids)).all()} if activity_ids else {}
    out = []
    for e in events:
        a = activities.get(e.activity_id)
        out.append({
            "id": e.id, "event_type": e.event_type, "from_value": e.from_value, "to_value": e.to_value,
            "actor_type": e.actor_type, "actor_id": e.actor_id, "note": e.note, "created_at": e.created_at,
            "activity_direction": a.direction if a else None,
            "activity_subject": a.subject if a else None,
        })
    return out


@router.get("/{deal_id}", response_model=DealOut,
           summary="Get a deal", description="Get a single deal by id. 404 if it's private and this user isn't admin/manager/owner/member. `value` is null without view_financials.")
def get_deal(deal_id: str, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d or not can_see(db, "deal", d, user):
        raise HTTPException(status_code=404, detail="Deal not found")
    return _to_out(db, d, user)


@router.post("", response_model=DealOut,
            summary="Create a deal", description="owner_id is always set server-side, never accepted directly from the payload -- the one lever a client has over it is `unassigned` (default false): false means the creator becomes owner (existing behavior), true means owner_id stays None and the deal sits in the shared inbox (D1). A service-account-authenticated create always leaves the deal unassigned/ownerless regardless of this flag (owner_id is a FK to users.id; a service account has no row there), and isn't auto-added as a member either -- EntityMembership.user_id is the same FK.")
def create_deal(payload: DealCreate, db: Session = Depends(get_db),
                user: User = Depends(require_capability("manage_deals"))):
    data = payload.model_dump(exclude={"unassigned"})
    owner_id = None if payload.unassigned else owner_id_for(user)
    check_owner_required(owner_id, data["stage"])
    d = Deal(**data, owner_id=owner_id, visibility=get_default_visibility(db))
    db.add(d)
    db.flush()
    log_event(db, "deal", d.id, "created", user)
    if isinstance(user, User):
        add_member(db, "deal", d.id, user.id, added_by=user)
    db.commit()
    db.refresh(d)
    return _to_out(db, d, user)


@router.put("/{deal_id}", response_model=DealOut,
           summary="Update a deal", description="Full replace of the editable fields. Logs a stage_changed event if stage differs from before. Rejects moving past `qualified` if the deal has no owner (D1/BL-4) -- claim it first.")
def update_deal(deal_id: str, payload: DealCreate, db: Session = Depends(get_db),
                user: User = Depends(require_capability("manage_deals"))):
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d or not can_see(db, "deal", d, user):
        raise HTTPException(status_code=404, detail="Deal not found")
    old_stage = d.stage
    if payload.stage != old_stage:
        check_owner_required(d.owner_id, payload.stage)
    for k, v in payload.model_dump(exclude={"unassigned"}).items():
        setattr(d, k, v)
    if d.stage != old_stage:
        log_event(db, "deal", d.id, "stage_changed", user, from_value=old_stage, to_value=d.stage)
        if d.stage == "won":
            create_project_from_won_deal(db, d, user)
    db.commit()
    db.refresh(d)
    return _to_out(db, d, user)


@router.patch("/{deal_id}/stage", response_model=DealOut,
             summary="Change deal stage", description="Sets stage and recomputes probability from a fixed stage->probability table. Rejects moving past `qualified` if the deal has no owner (D1/BL-4) -- claim it first. Otherwise any stage can move to any other stage; no other transition guard. Logs a stage_changed event. Moving into `won` auto-creates a Project from the deal (4.3) -- idempotent, so re-triggering won doesn't spawn a second one.")
def update_stage(deal_id: str, payload: StageUpdate, db: Session = Depends(get_db),
                 user: User = Depends(require_capability("manage_deals"))):
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d or not can_see(db, "deal", d, user):
        raise HTTPException(status_code=404, detail="Deal not found")
    old_stage = d.stage
    if payload.stage != old_stage:
        check_owner_required(d.owner_id, payload.stage)
    d.stage = payload.stage
    d.probability = STAGE_PROBABILITY.get(payload.stage, d.probability)
    if d.stage != old_stage:
        log_event(db, "deal", d.id, "stage_changed", user, from_value=old_stage, to_value=d.stage)
        if d.stage == "won":
            create_project_from_won_deal(db, d, user)
    db.commit()
    db.refresh(d)
    return _to_out(db, d, user)


@router.patch("/{deal_id}/visibility", response_model=DealOut,
             summary="Change deal visibility", description="Set public/private. A separate capability (set_visibility) from manage_deals, so a role that can write deals doesn't automatically get to change who can see one. Logs a visibility_changed event.")
def update_visibility(deal_id: str, payload: VisibilityUpdate, db: Session = Depends(get_db),
                      user: User = Depends(require_capability("set_visibility"))):
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d or not can_see(db, "deal", d, user):
        raise HTTPException(status_code=404, detail="Deal not found")
    old_visibility = d.visibility
    d.visibility = payload.visibility
    if d.visibility != old_visibility:
        log_event(db, "deal", d.id, "visibility_changed", user, from_value=old_visibility, to_value=d.visibility)
    db.commit()
    db.refresh(d)
    return _to_out(db, d, user)


@router.patch("/{deal_id}/claim", response_model=DealOut,
             summary="Claim an unassigned deal", description="Sets the caller as owner of a deal currently sitting in the shared inbox (owner_id IS NULL) and records claimed_at. Logs a claimed event. 400 if the deal already has an owner -- use PATCH /owner (reassign_owner capability) to reassign an already-owned deal instead.")
def claim_deal(deal_id: str, db: Session = Depends(get_db),
              user: User = Depends(require_capability("manage_deals"))):
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d or not can_see(db, "deal", d, user):
        raise HTTPException(status_code=404, detail="Deal not found")
    if d.owner_id:
        raise HTTPException(status_code=400, detail="Deal already has an owner")
    if not isinstance(user, User):
        raise HTTPException(status_code=400, detail="A service account cannot claim ownership of a deal")
    d.owner_id = user.id
    d.claimed_at = datetime.now(timezone.utc)
    log_event(db, "deal", d.id, "claimed", user, to_value=user.id)
    add_member(db, "deal", d.id, user.id, added_by=user)
    db.commit()
    db.refresh(d)
    return _to_out(db, d, user)


@router.patch("/{deal_id}/owner", response_model=DealOut,
             summary="Reassign a deal's owner", description="Explicitly set a deal's owner to a different user, unlike /claim (which only works on an unassigned deal and always sets the caller). Requires reassign_owner. Logs an owner_changed event and auto-tags the new owner as a member.")
def reassign_deal_owner(deal_id: str, payload: OwnerUpdate, db: Session = Depends(get_db),
                        user: User = Depends(require_capability("reassign_owner"))):
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d or not can_see(db, "deal", d, user):
        raise HTTPException(status_code=404, detail="Deal not found")
    target = db.query(User).filter(User.id == payload.owner_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    old_owner = d.owner_id
    d.owner_id = target.id
    if not d.claimed_at:
        d.claimed_at = datetime.now(timezone.utc)
    log_event(db, "deal", d.id, "owner_changed", user, from_value=old_owner, to_value=target.id)
    add_member(db, "deal", d.id, target.id, added_by=user)
    db.commit()
    db.refresh(d)
    return _to_out(db, d, user)


@router.patch("/{deal_id}/ball-in-court", response_model=DealOut,
             summary="Manually set ball-in-court", description="Override who the ball is with (us/them/none) -- the value is otherwise set automatically whenever a directed Activity is logged against the deal. Requires manage_deals. Logs a ball_in_court_changed event.")
def update_ball_in_court(deal_id: str, payload: BallInCourtUpdate, db: Session = Depends(get_db),
                        user: User = Depends(require_capability("manage_deals"))):
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d or not can_see(db, "deal", d, user):
        raise HTTPException(status_code=404, detail="Deal not found")
    old_value = d.ball_in_court
    d.ball_in_court = payload.ball_in_court
    if d.ball_in_court != old_value:
        log_event(db, "deal", d.id, "ball_in_court_changed", user,
                 from_value=old_value, to_value=d.ball_in_court)
    db.commit()
    db.refresh(d)
    return _to_out(db, d, user)


@router.get("/{deal_id}/members",
           summary="List deal members", description="Members of a deal (the owner is auto-included from creation). Membership only matters for `private` deals -- on a `public` deal it's informational.")
def list_deal_members(deal_id: str, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d or not can_see(db, "deal", d, user):
        raise HTTPException(status_code=404, detail="Deal not found")
    rows = list_members(db, "deal", deal_id)
    users = {u.id: u for u in db.query(User).filter(User.id.in_([m.user_id for m in rows])).all()}
    return [{
        "user_id": m.user_id,
        "name": users[m.user_id].name if m.user_id in users else None,
        "email": users[m.user_id].email if m.user_id in users else None,
        "added_by": m.added_by, "added_at": m.added_at,
    } for m in rows]


@router.post("/{deal_id}/members",
            summary="Invite a member", description="Add a user as a member of this deal, granting them access if it's `private`. Requires invite_members.")
def add_deal_member(deal_id: str, payload: MemberAdd, db: Session = Depends(get_db),
                    user: User = Depends(require_capability("invite_members"))):
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d or not can_see(db, "deal", d, user):
        raise HTTPException(status_code=404, detail="Deal not found")
    if not db.query(User).filter(User.id == payload.user_id).first():
        raise HTTPException(status_code=404, detail="User not found")
    add_member(db, "deal", deal_id, payload.user_id, added_by=user)
    db.commit()
    return {"success": True}


@router.delete("/{deal_id}/members/{user_id}",
              summary="Remove a member", description="Requires invite_members. The deal's owner cannot be removed from membership.")
def remove_deal_member(deal_id: str, user_id: str, db: Session = Depends(get_db),
                       user: User = Depends(require_capability("invite_members"))):
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d or not can_see(db, "deal", d, user):
        raise HTTPException(status_code=404, detail="Deal not found")
    if d.owner_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot remove the owner from membership")
    remove_member(db, "deal", deal_id, user_id)
    db.commit()
    return {"success": True}


@router.delete("/{deal_id}",
              summary="Delete a deal", description="Hard delete; nulls out deal_id on any activities that referenced it first. Logs a deleted event.")
def delete_deal(deal_id: str, db: Session = Depends(get_db),
                user: User = Depends(require_capability("manage_deals"))):
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d or not can_see(db, "deal", d, user):
        raise HTTPException(status_code=404, detail="Deal not found")
    # Null out child references before deleting
    db.query(Activity).filter(Activity.deal_id == deal_id).update({Activity.deal_id: None})
    log_event(db, "deal", d.id, "deleted", user)
    db.delete(d)
    db.commit()
    return {"success": True}
