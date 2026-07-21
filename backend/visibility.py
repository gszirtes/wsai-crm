from sqlalchemy import or_, exists
from sqlalchemy.orm import Session
from models import EntityMembership, User

# Deal/Project are the only visibility-scoped entities in this phase (an
# accepted simplification the plan states explicitly: contacts/companies stay
# visible to every logged-in user). admin/manager always see everything;
# everyone else sees public rows plus private rows they're a member of.
FULL_VISIBILITY_ROLES = ("admin", "manager")


def visibility_filter(db: Session, model, entity_type: str, user: User):
    """SQLAlchemy filter clause for `model` (Deal or Project), scoping rows
    to what `user` can see. Pass straight into .filter(...) on a query
    against `model` -- the EXISTS subquery correlates automatically to the
    outer query's `model` since we never call .select_from() on it here.
    """
    if user.role in FULL_VISIBILITY_ROLES:
        return True
    member_exists = exists().where(
        EntityMembership.entity_type == entity_type,
        EntityMembership.entity_id == model.id,
        EntityMembership.user_id == user.id,
    )
    return or_(model.visibility == "public", member_exists)


def can_see(db: Session, entity_type: str, entity, user: User) -> bool:
    """Same rule as visibility_filter, applied to a single already-fetched
    row (e.g. after a .filter(Model.id == id).first()) rather than as a
    query-level filter -- for the detail endpoints, which need a 404 (not an
    empty list) when the row exists but isn't visible to this user."""
    if user.role in FULL_VISIBILITY_ROLES:
        return True
    if entity.visibility == "public":
        return True
    return db.query(EntityMembership).filter(
        EntityMembership.entity_type == entity_type,
        EntityMembership.entity_id == entity.id,
        EntityMembership.user_id == user.id,
    ).first() is not None
