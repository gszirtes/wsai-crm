from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, EmailStr, Field

# Allowed enum values
DealStage = Literal["lead", "qualified", "proposal", "negotiation", "won", "lost"]
ContactStatus = Literal["lead", "prospect", "customer", "inactive"]
ProjectStatus = Literal["planning", "active", "on_hold", "completed", "cancelled"]
ActivityType = Literal["call", "email", "meeting", "task", "note"]
ActivityDirection = Literal["inbound", "outbound", "internal"]
ProjectPriority = Literal["low", "medium", "high"]
UserRole = Literal["admin", "manager", "user", "guest"]
Visibility = Literal["public", "private"]


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
    currency: Optional[str] = "EUR"
    stage: Optional[DealStage] = "lead"
    probability: Optional[int] = 10
    expected_close: Optional[datetime] = None
    notes: Optional[str] = None
    company_id: Optional[str] = None
    contact_id: Optional[str] = None


class DealCreate(DealBase):
    pass


class DealOut(DealBase):
    id: str
    owner_id: Optional[str] = None
    visibility: Visibility = "public"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StageUpdate(BaseModel):
    stage: DealStage


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
    currency: Optional[str] = "EUR"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    company_id: Optional[str] = None
    contact_id: Optional[str] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectOut(ProjectBase):
    id: str
    owner_id: Optional[str] = None
    visibility: Visibility = "public"
    created_at: Optional[datetime] = None
    logged_hours: Optional[float] = 0
    health: Optional[str] = None

    class Config:
        from_attributes = True


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


class LocaleUpdate(BaseModel):
    locale: Literal["en", "hu"]
