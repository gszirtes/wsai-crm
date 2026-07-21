from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from models import EntityMembership
from utils import owner_id_for


def is_member(db: Session, entity_type: str, entity_id: str, user_id: str) -> bool:
    return db.query(EntityMembership).filter(
        EntityMembership.entity_type == entity_type,
        EntityMembership.entity_id == entity_id,
        EntityMembership.user_id == user_id,
    ).first() is not None


def add_member(db: Session, entity_type: str, entity_id: str, user_id: str, added_by) -> EntityMembership:
    """Idempotent: adding an existing member returns the existing row rather
    than raising on the unique constraint."""
    existing = db.query(EntityMembership).filter(
        EntityMembership.entity_type == entity_type,
        EntityMembership.entity_id == entity_id,
        EntityMembership.user_id == user_id,
    ).first()
    if existing:
        return existing
    m = EntityMembership(entity_type=entity_type, entity_id=entity_id, user_id=user_id,
                         added_by=owner_id_for(added_by) if added_by is not None else None)
    try:
        # SAVEPOINT, not a plain flush: a concurrent invite of the same user
        # can race the pre-check above and hit uq_entity_membership on this
        # insert. begin_nested() lets that failure unwind just this insert
        # rather than db.rollback()-ing the whole request's transaction
        # (which would also discard any earlier uncommitted work in the same
        # session, e.g. a log_event() call made just before this one).
        with db.begin_nested():
            db.add(m)
            db.flush()
    except IntegrityError:
        return db.query(EntityMembership).filter(
            EntityMembership.entity_type == entity_type,
            EntityMembership.entity_id == entity_id,
            EntityMembership.user_id == user_id,
        ).first()
    return m


def remove_member(db: Session, entity_type: str, entity_id: str, user_id: str):
    db.query(EntityMembership).filter(
        EntityMembership.entity_type == entity_type,
        EntityMembership.entity_id == entity_id,
        EntityMembership.user_id == user_id,
    ).delete()


def list_members(db: Session, entity_type: str, entity_id: str):
    return db.query(EntityMembership).filter(
        EntityMembership.entity_type == entity_type,
        EntityMembership.entity_id == entity_id,
    ).order_by(EntityMembership.added_at.asc()).all()
