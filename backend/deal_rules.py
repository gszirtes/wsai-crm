from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models import Deal, Project
from utils import log_event
from membership import add_member, list_members
from milestone_templates import instantiate_template, DEFAULT_TEMPLATE

# D1/BL-4: an unowned lead may sit in the shared inbox but can't advance past
# "qualified" -- these are the stages that require owner_id to already be set.
OWNER_REQUIRED_STAGES = {"proposal", "negotiation", "won", "lost"}


def check_owner_required(owner_id: str, new_stage: str):
    """Raises 400 if `new_stage` requires an owner (D1/BL-4) and none is set.
    Must be enforced on every path that can set a Deal's stage -- create
    included, not just the update endpoints."""
    if new_stage in OWNER_REQUIRED_STAGES and not owner_id:
        raise HTTPException(status_code=400,
                            detail="This deal needs an owner (claim it first) before it can move past qualified")


# 2.2: directed Activity creation updates ball-in-court automatically.
# internal (or no direction) doesn't move the needle either way.
DIRECTION_TO_BALL_IN_COURT = {"inbound": "us", "outbound": "them"}


def apply_ball_in_court_for_activity(db: Session, deal_id: str, direction: str, actor):
    """Called from activities.py on a directed Activity create. Not a
    visibility/existence check (activities.py already resolved+can_see'd
    the deal before calling this) -- just applies the state change."""
    new_value = DIRECTION_TO_BALL_IN_COURT.get(direction)
    if not new_value:
        return
    d = db.query(Deal).filter(Deal.id == deal_id).first()
    if not d:
        return
    old_value = d.ball_in_court
    d.last_contact_at = datetime.now(timezone.utc)
    d.ball_in_court = new_value
    if new_value != old_value:
        # D4: a "pass" is counted from these direction changes in the
        # Fazis 2.3 deal-flow analytics.
        log_event(db, "deal", d.id, "ball_in_court_changed", actor,
                 from_value=old_value, to_value=new_value)


# 4.3: won deals automatically spawn a Project. Called from deals.py's stage
# transition paths (PATCH /stage and PUT) right after a deal's stage actually
# becomes "won" -- both paths already ran check_owner_required, so d.owner_id
# is guaranteed set by the time this runs.
def create_project_from_won_deal(db: Session, deal: Deal, actor):
    """Idempotent: if a Project already points at this deal (deal_id), does
    nothing and returns None instead of creating a second one -- a deal can
    be moved to won, off won, and back to won again without spawning
    duplicate projects."""
    if db.query(Project).filter(Project.deal_id == deal.id).first():
        return None

    # A double-sided lead's contracting party (contract_company_id/
    # contract_contact_id) is who actually pays -- if set, that's who the
    # spawned project should be billed to, not the day-to-day contact.
    company_id = deal.contract_company_id if deal.lead_type == "double" and deal.contract_company_id else deal.company_id
    contact_id = deal.contract_contact_id if deal.lead_type == "double" and deal.contract_contact_id else deal.contact_id

    p = Project(
        name=deal.title, company_id=company_id, contact_id=contact_id,
        budget=deal.value, currency=deal.currency, owner_id=deal.owner_id,
        visibility=deal.visibility, deal_id=deal.id,
    )
    db.add(p)
    db.flush()
    for m in instantiate_template(DEFAULT_TEMPLATE, p.id):
        db.add(m)
    log_event(db, "project", p.id, "created", actor, note=f"auto-created from deal {deal.id}")
    # Carry the deal's membership over so the same people already granted
    # access to a private deal aren't suddenly locked out of the project it
    # spawns (matters only when visibility="private" -- add_member is a
    # harmless no-op for a public project's access checks).
    for member in list_members(db, "deal", deal.id):
        add_member(db, "project", p.id, member.user_id, added_by=actor)
    return p
