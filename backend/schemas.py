from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, EmailStr, Field, model_validator

# Allowed enum values
DealStage = Literal["lead", "qualified", "proposal", "negotiation", "won", "lost"]
ContactStatus = Literal["lead", "prospect", "customer", "inactive"]
ProjectStatus = Literal["planning", "active", "on_hold", "completed", "cancelled"]
ActivityType = Literal["call", "email", "meeting", "task", "note"]
ActivityDirection = Literal["inbound", "outbound", "internal"]
ProjectPriority = Literal["low", "medium", "high"]
UserRole = Literal["admin", "manager", "user", "guest"]
Visibility = Literal["public", "private"]
DealSource = Literal["inbound", "outreach", "referral", "other"]
BallInCourt = Literal["us", "them", "none"]
LeadType = Literal["single", "double"]
Currency = Literal["EUR", "HUF"]
MilestoneWorkStatus = Literal["in_progress", "client_review", "accepted"]
MilestonePaymentStatus = Literal["not_due", "invoiceable", "invoiced", "paid"]


# ---------- Auth ----------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str
    role: Optional[UserRole] = "user"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: UserRole
    avatar_url: Optional[str] = None
    locale: str = "en"
    auth_provider: str = "local"
    google_connected: bool = False
    active: bool = True
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[UserRole] = None
    locale: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = None


# ---------- Company ----------
class CompanyBase(BaseModel):
    name: str
    industry: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    size: Optional[str] = None
    notes: Optional[str] = None


class CompanyCreate(CompanyBase):
    pass


class CompanyOut(CompanyBase):
    id: str
    owner_id: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- Contact ----------
class ContactBase(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    status: Optional[ContactStatus] = "lead"
    tags: Optional[List[str]] = []
    notes: Optional[str] = None
    company_id: Optional[str] = None


class ContactCreate(ContactBase):
    pass


class ContactOut(ContactBase):
    id: str
    owner_id: Optional[str] = None
    company_name: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- Deal ----------
class DealBase(BaseModel):
    title: str
    value: Optional[float] = 0
    currency: Optional[Currency] = "EUR"
    stage: Optional[DealStage] = "lead"
    probability: Optional[int] = 10
    expected_close: Optional[datetime] = None
    notes: Optional[str] = None
    company_id: Optional[str] = None
    contact_id: Optional[str] = None
    source: Optional[DealSource] = None
    lead_type: Optional[LeadType] = "single"
    # Only meaningful when lead_type="double": the paying/contracting party,
    # when it differs from the day-to-day contact above. Unvalidated against
    # lead_type on purpose -- Fazis 3 adds the fields, not a stage guard.
    contract_company_id: Optional[str] = None
    contract_contact_id: Optional[str] = None
    referred_by_contact_id: Optional[str] = None


class DealCreate(DealBase):
    # Create-time-only flag, not a Deal column: False (default) means the
    # creator becomes owner (existing behavior); True means owner_id stays
    # None (shared/unassigned inbox). owner_id itself is still never
    # accepted as client input -- this is the one lever a client has over
    # it. update_deal (PUT) reuses this schema too but explicitly excludes
    # this field from the update, since it only means something at creation.
    unassigned: bool = False


class DealOut(DealBase):
    id: str
    owner_id: Optional[str] = None
    visibility: Visibility = "public"
    claimed_at: Optional[datetime] = None
    last_contact_at: Optional[datetime] = None
    ball_in_court: Optional[BallInCourt] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StageUpdate(BaseModel):
    stage: DealStage


class BallInCourtUpdate(BaseModel):
    ball_in_court: BallInCourt


class OwnerUpdate(BaseModel):
    owner_id: str


class VisibilityUpdate(BaseModel):
    visibility: Visibility


class MemberAdd(BaseModel):
    user_id: str


class MemberOut(BaseModel):
    user_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    added_by: Optional[str] = None
    added_at: Optional[datetime] = None


# ---------- Project ----------
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: Optional[ProjectStatus] = "planning"
    priority: Optional[ProjectPriority] = "medium"
    budget: Optional[float] = 0
    estimated_hours: Optional[float] = 0
    hourly_rate: Optional[float] = 0
    currency: Optional[Currency] = "EUR"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    company_id: Optional[str] = None
    contact_id: Optional[str] = None


class ProjectCreate(ProjectBase):
    # Create-time-only: which starter milestone set to pre-fill (plan 4.1).
    # Not a Project column -- consumed once by create_project to seed
    # Milestone rows, then the project has no further memory of which
    # template it started from (the milestones themselves are freely
    # editable afterward).
    milestone_template: Optional[Literal["single_final", "deposit_final", "milestones"]] = "single_final"


class ProjectOut(ProjectBase):
    id: str
    owner_id: Optional[str] = None
    deal_id: Optional[str] = None
    visibility: Visibility = "public"
    created_at: Optional[datetime] = None
    logged_hours: Optional[float] = 0
    health: Optional[str] = None

    class Config:
        from_attributes = True


class MilestoneBase(BaseModel):
    name: str
    order_index: Optional[int] = 0
    due_date: Optional[datetime] = None
    amount: Optional[float] = None
    percentage: Optional[float] = None
    work_status: Optional[MilestoneWorkStatus] = "in_progress"
    payment_status: Optional[MilestonePaymentStatus] = "not_due"

    @model_validator(mode="after")
    def _amount_xor_percentage(self):
        # D11: exactly one of amount/percentage must be set, never both,
        # never neither -- a milestone with no way to size itself, or two
        # conflicting ones, is a data-entry error, not a valid state.
        if (self.amount is None) == (self.percentage is None):
            raise ValueError("Exactly one of amount or percentage must be set")
        return self


class MilestoneCreate(MilestoneBase):
    pass


class MilestoneOut(MilestoneBase):
    id: str
    project_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MilestoneStatusUpdate(BaseModel):
    work_status: Optional[MilestoneWorkStatus] = None
    payment_status: Optional[MilestonePaymentStatus] = None

    @model_validator(mode="after")
    def _at_least_one(self):
        if self.work_status is None and self.payment_status is None:
            raise ValueError("At least one of work_status or payment_status must be set")
        return self


class TimeEntryCreate(BaseModel):
    hours: float
    description: Optional[str] = None
    billable: Optional[bool] = True
    entry_date: Optional[datetime] = None


class TimeEntryOut(BaseModel):
    id: str
    project_id: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    hours: float
    description: Optional[str] = None
    billable: bool = True
    entry_date: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- Activity ----------
class ActivityBase(BaseModel):
    type: Optional[ActivityType] = "task"
    direction: Optional[ActivityDirection] = None
    subject: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    completed: Optional[bool] = False
    contact_id: Optional[str] = None
    company_id: Optional[str] = None
    deal_id: Optional[str] = None
    project_id: Optional[str] = None


class ActivityCreate(ActivityBase):
    pass


class ActivityOut(ActivityBase):
    id: str
    owner_id: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- AI ----------
class AICommandRequest(BaseModel):
    command: str


class SettingUpdate(BaseModel):
    openrouter_api_key: Optional[str] = None
    openrouter_model: Optional[str] = None
    default_visibility: Optional[Visibility] = None


# ---------- Capability matrix (Phase 1 access control) ----------
class RoleCapabilities(BaseModel):
    view_financials: bool
    manage_deals: bool
    manage_projects: bool
    invite_members: bool
    set_visibility: bool
    reassign_owner: bool
    view_all_reports: bool


class CapabilityMatrix(BaseModel):
    admin: RoleCapabilities
    manager: RoleCapabilities
    user: RoleCapabilities
    guest: RoleCapabilities


# ---------- SLA thresholds (D7, Phase 2) ----------
class ThresholdSettings(BaseModel):
    unassigned_days: int = Field(ge=0)
    awaiting_response_days: int = Field(ge=0)
    stale_days: int = Field(ge=0)


class LocaleUpdate(BaseModel):
    locale: Literal["en", "hu"]


# ---------- Service accounts (Phase 1 MCP-enabler) ----------
class ServiceAccountCreate(BaseModel):
    name: str
    role: UserRole = "user"


class ServiceAccountOut(BaseModel):
    id: str
    name: str
    role: UserRole
    active: bool
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ServiceAccountCreated(ServiceAccountOut):
    api_key: str  # plaintext, present only in the create response -- never retrievable again


class ServiceAccountUpdate(BaseModel):
    role: Optional[UserRole] = None
    active: Optional[bool] = None
