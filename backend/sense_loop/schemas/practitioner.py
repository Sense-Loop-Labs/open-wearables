"""Practitioner schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class PractitionerBase(BaseModel):
    """Base practitioner fields."""

    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: str | None = Field(None, max_length=50)
    npi_number: str | None = Field(None, max_length=50)
    credentials: str | None = Field(None, max_length=100)


class PractitionerCreate(PractitionerBase):
    """Schema for creating a practitioner (admin use)."""

    password: str = Field(..., min_length=12, max_length=128)
    organization_id: UUID
    role_code: str = Field(..., max_length=50)


class PractitionerUpdate(BaseModel):
    """Schema for updating a practitioner."""

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    phone: str | None = Field(None, max_length=50)
    npi_number: str | None = Field(None, max_length=50)
    credentials: str | None = Field(None, max_length=100)
    is_active: bool | None = None


class PractitionerRoleResponse(BaseModel):
    """Practitioner role within an organization."""

    id: UUID
    organization_id: UUID
    organization_name: str
    role_code: str
    role_display_name: str
    is_active: bool
    is_primary: bool
    accepted_at: datetime | None = None


class PractitionerResponse(BaseModel):
    """Schema for practitioner response."""

    id: UUID
    email: str
    first_name: str
    last_name: str
    full_name: str
    display_name: str
    phone: str | None = None
    npi_number: str | None = None
    credentials: str | None = None

    is_active: bool
    email_verified_at: datetime | None = None
    last_login_at: datetime | None = None

    created_at: datetime

    # Roles in organizations
    roles: list[PractitionerRoleResponse] = []

    class Config:
        from_attributes = True


class PractitionerListResponse(BaseModel):
    """Schema for paginated practitioner list."""

    items: list[PractitionerResponse]
    total: int
    page: int
    page_size: int
    pages: int


# Invitation Schemas


class InviteRequest(BaseModel):
    """Request to invite a new clinician."""

    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role_code: str = Field(..., max_length=50)
    organization_id: UUID


class InviteResponse(BaseModel):
    """Response from sending an invitation."""

    success: bool
    invite_id: UUID | None = None
    email: str | None = None
    message: str


class PendingInvite(BaseModel):
    """Pending invitation details."""

    id: UUID
    email: str
    first_name: str
    last_name: str
    full_name: str
    role_code: str
    organization_id: UUID
    organization_name: str
    expires_at: datetime
    is_expired: bool
    is_pending: bool
    created_at: datetime


class AcceptInviteRequest(BaseModel):
    """Request to accept an invitation."""

    invite_id: UUID
    invite_secret: str
    password: str = Field(..., min_length=12, max_length=128)
    password_confirm: str = Field(..., min_length=12, max_length=128)


class AcceptInviteResponse(BaseModel):
    """Response from accepting an invitation."""

    success: bool
    practitioner_id: UUID | None = None
    message: str


class RoleDefinitionResponse(BaseModel):
    """Schema for role definition response."""

    id: UUID
    code: str
    display_name: str

    # Permission flags
    can_manage_patients: bool
    can_manage_alerts: bool
    can_resolve_alerts: bool
    can_acknowledge_alerts: bool
    can_manage_care_plans: bool
    can_manage_clinicians: bool
    can_manage_org_settings: bool
    can_view_audit_logs: bool
    can_manage_alert_protocols: bool
    can_export_data: bool

    # Meta
    is_system_role: bool
    is_active: bool
    privilege_level: int

    class Config:
        from_attributes = True
