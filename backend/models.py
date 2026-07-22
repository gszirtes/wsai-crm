import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Float, Boolean, DateTime, ForeignKey, Integer, Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from database import Base


def gen_id():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_id)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="user")  # admin, manager, user, guest
    avatar_url = Column(String, nullable=True)
    locale = Column(String, default="en")
    auth_provider = Column(String, default="local")  # local, google
    google_connected = Column(Boolean, default=False)
    google_email = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class Company(Base):
    __tablename__ = "companies"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False, index=True)
    industry = Column(String, nullable=True)
    website = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    address = Column(String, nullable=True)
    size = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    owner_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    contacts = relationship("Contact", back_populates="company")


class Contact(Base):
    __tablename__ = "contacts"
    id = Column(String, primary_key=True, default=gen_id)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True)
    title = Column(String, nullable=True)
    status = Column(String, default="lead")  # lead, prospect, customer, inactive
    tags = Column(JSONB, default=list)
    notes = Column(Text, nullable=True)
    company_id = Column(String, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    owner_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    company = relationship("Company", back_populates="contacts")


class Deal(Base):
    __tablename__ = "deals"
    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String, nullable=False)
    value = Column(Float, default=0)
    currency = Column(String, default="EUR")
    stage = Column(String, default="lead")  # lead, qualified, proposal, negotiation, won, lost
    probability = Column(Integer, default=10)
    expected_close = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    visibility = Column(String, nullable=False, default="public", server_default="public")  # public, private
    company_id = Column(String, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    contact_id = Column(String, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    owner_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    source = Column(String, nullable=True)  # inbound, outreach, referral, other
    last_contact_at = Column(DateTime(timezone=True), nullable=True)
    ball_in_court = Column(String, nullable=True)  # us, them, none
    lead_type = Column(String, nullable=False, default="single", server_default="single")  # single, double
    contract_company_id = Column(String, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    contract_contact_id = Column(String, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    referred_by_contact_id = Column(String, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="planning")  # planning, active, on_hold, completed, cancelled
    priority = Column(String, default="medium")  # low, medium, high
    budget = Column(Float, default=0)
    estimated_hours = Column(Float, default=0)
    hourly_rate = Column(Float, default=0)
    currency = Column(String, default="EUR")
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    visibility = Column(String, nullable=False, default="public", server_default="public")  # public, private
    company_id = Column(String, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    contact_id = Column(String, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    owner_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    deal_id = Column(String, ForeignKey("deals.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Milestone(Base):
    """Client-facing billing unit for a fixed-price project (Phase 4),
    replacing ad-hoc hourly invoicing. work_status and payment_status are
    independently settable and reversible in either direction -- "we shipped
    it" and "we got paid for it" are different facts that don't always move
    together (a client can pay a deposit before work starts, or delay
    payment after acceptance).
    """
    __tablename__ = "milestones"
    id = Column(String, primary_key=True, default=gen_id)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    order_index = Column(Integer, nullable=False, default=0)
    due_date = Column(DateTime(timezone=True), nullable=True)
    amount = Column(Float, nullable=True)
    percentage = Column(Float, nullable=True)
    work_status = Column(String, nullable=False, default="in_progress")  # in_progress, client_review, accepted
    payment_status = Column(String, nullable=False, default="not_due")  # not_due, invoiceable, invoiced, paid
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Activity(Base):
    __tablename__ = "activities"
    id = Column(String, primary_key=True, default=gen_id)
    type = Column(String, default="task")  # call, email, meeting, task, note
    direction = Column(String, nullable=True)  # inbound, outbound, internal, or NULL
    subject = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    completed = Column(Boolean, default=False)
    contact_id = Column(String, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    company_id = Column(String, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    deal_id = Column(String, ForeignKey("deals.id", ondelete="SET NULL"), nullable=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    owner_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class TimeEntry(Base):
    __tablename__ = "time_entries"
    id = Column(String, primary_key=True, default=gen_id)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    hours = Column(Float, default=0)
    description = Column(String, nullable=True)
    billable = Column(Boolean, default=True)
    entry_date = Column(DateTime(timezone=True), default=utcnow)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key = Column(String, index=True)
    type = Column(String, default="info")  # auto_overdue, auto_due_today, auto_project_risk, info
    title = Column(String, nullable=False)
    body = Column(String, nullable=True)
    link = Column(String, nullable=True)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class EventLog(Base):
    """Generic, append-only audit trail — never updated or deleted in place.

    entity_id has no DB foreign key on purpose: entity_type varies row to row
    (deal, project, activity, ...), so a single column can't point at a single
    table. Integrity (that entity_id actually refers to a row of entity_type)
    is the writer's responsibility (always go through log_event()), not the
    DB's. Rows outlive their entity: a hard-deleted parent leaves its history
    in place for audit purposes.
    """
    __tablename__ = "event_logs"
    id = Column(String, primary_key=True, default=gen_id)
    entity_type = Column(String, nullable=False, index=True)  # deal, project, activity, milestone, ...
    entity_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)  # created, deleted, claimed, stage_changed, status_changed,
                                                  # activity_logged, owner_changed, visibility_changed
    from_value = Column(String, nullable=True)
    to_value = Column(String, nullable=True)
    actor_type = Column(String, nullable=False)  # user, service
    actor_id = Column(String, nullable=True)
    activity_id = Column(String, ForeignKey("activities.id", ondelete="SET NULL"), nullable=True)
    note = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, index=True)

    __table_args__ = (
        Index("ix_event_logs_entity_type_entity_id_created_at", "entity_type", "entity_id", "created_at"),
    )


class EntityMembership(Base):
    """Generic membership/invite table (Phase 1 access control) -- who can see
    a `private` Deal/Project beyond its owner. Same entity_type+entity_id
    pattern as EventLog, for the same reason: one table reused across
    entities instead of a membership table per entity type.
    """
    __tablename__ = "entity_memberships"
    id = Column(String, primary_key=True, default=gen_id)
    entity_type = Column(String, nullable=False, index=True)  # deal, project
    entity_id = Column(String, nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    added_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    added_at = Column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "user_id", name="uq_entity_membership"),
        Index("ix_entity_memberships_entity_type_entity_id", "entity_type", "entity_id"),
    )


class AppSetting(Base):
    __tablename__ = "app_settings"
    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True)


class AICommandLog(Base):
    __tablename__ = "ai_command_logs"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    command = Column(Text, nullable=False)
    action = Column(String, nullable=True)
    response = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class ServiceAccount(Base):
    """API-key principal for machine/agent access (Phase 1 MCP-enabler --
    the actual MCP server is Phase 6). Plugs into the exact same role +
    capability model as a human User: `role` is checked by require_role/
    require_capability/has_capability identically, since those only ever
    read `.role` off whatever principal get_current_user() returned. Never
    stores the raw key -- key_hash is a SHA-256 digest, looked up by exact
    match (the key itself is a high-entropy random token, not a
    user-chosen password, so bcrypt's slow-hash brute-force protection
    isn't the relevant property here; fast, indexed exact-match lookup is).
    """
    __tablename__ = "service_accounts"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    key_hash = Column(String, nullable=False, unique=True, index=True)
    role = Column(String, nullable=False, default="user")  # admin, manager, user, guest -- same as User.role
    active = Column(Boolean, default=True)
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
