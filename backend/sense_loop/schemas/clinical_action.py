"""Clinical action schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


ActionType = Literal["phone", "in-person", "order", "education", "escalation", "note"]


class ClinicalActionCreate(BaseModel):
    """Schema for creating a clinical action."""

    action_type: ActionType = Field(..., description="Type of clinical action")
    notes: str | None = Field(None, description="Notes about the action")
    related_alert_ids: list[UUID] | None = Field(
        None, description="IDs of related alerts"
    )


class ClinicalActionResponse(BaseModel):
    """Schema for clinical action response."""

    id: UUID
    patient_id: UUID
    organization_id: UUID
    practitioner_id: UUID
    action_type: str
    category_display: str
    notes: str | None
    practitioner_name: str
    related_alert_ids: list[UUID] | None
    created_at: datetime

    class Config:
        from_attributes = True


class ClinicalActionListResponse(BaseModel):
    """Schema for paginated clinical action list."""

    items: list[ClinicalActionResponse]
    total: int
    page: int
    page_size: int
    pages: int
