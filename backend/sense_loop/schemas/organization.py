"""Organization schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class OrganizationBase(BaseModel):
    """Base organization fields."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = None

    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(None, max_length=100)
    address: str | None = None


class OrganizationCreate(OrganizationBase):
    """Schema for creating an organization."""

    settings: dict | None = None


class OrganizationUpdate(BaseModel):
    """Schema for updating an organization."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(None, max_length=100)
    address: str | None = None
    settings: dict | None = None
    is_active: bool | None = None


class OrganizationStats(BaseModel):
    """Organization statistics."""

    total_patients: int = 0
    active_patients: int = 0
    total_practitioners: int = 0
    active_alerts: int = 0
    critical_alerts: int = 0


class OrganizationResponse(BaseModel):
    """Schema for organization response."""

    id: UUID
    name: str
    slug: str
    description: str | None = None

    contact_email: str | None = None
    contact_phone: str | None = None
    address: str | None = None

    settings: dict | None = None
    is_active: bool

    created_at: datetime

    # Optional stats (included in detail view)
    stats: OrganizationStats | None = None

    class Config:
        from_attributes = True


class OrganizationListResponse(BaseModel):
    """Schema for paginated organization list."""

    items: list[OrganizationResponse]
    total: int
    page: int
    page_size: int
    pages: int
