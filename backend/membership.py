from sqlalchemy.orm import Session
from models import EntityMembership


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
                         added_by=added_by.id if added_by is not None else None)
    db.add(m)
    db.flush()
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
