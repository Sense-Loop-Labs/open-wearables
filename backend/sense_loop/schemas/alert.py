"""Alert schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AlertResponse(BaseModel):
    """Schema for alert response."""

    id: UUID
    patient_id: UUID
    organization_id: UUID

    title: str
    message: str | None = None
    severity: str  # info, warning, critical
    category: str  # vital_sign, questionnaire, care_plan, system

    status: str  # active, acknowledged, resolved, auto_resolved, escalated

    triggered_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    escalated_at: datetime | None = None

    # Attribution
    acknowledged_by_id: UUID | None = None
    acknowledged_by_name: str | None = None
    resolved_by_id: UUID | None = None
    resolved_by_name: str | None = None

    resolution_notes: str | None = None
    resolution_type: str | None = None

    # Vital details
    vital_type: str | None = None
    observed_value: float | None = None
    threshold_breached: str | None = None
    threshold_value: float | None = None

    # Context
    days_post_surgery: int | None = None
    patient_context: str | None = None

    # Traceability
    protocol_id: UUID | None = None
    protocol_version: int | None = None
    rule_id: UUID | None = None

    # Patient info (for list views)
    patient_name: str | None = None
    patient_mrn: str | None = None

    created_at: datetime

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    """Schema for paginated alert list."""

    items: list[AlertResponse]
    total: int
    page: int
    page_size: int
    pages: int


class AlertAcknowledgeRequest(BaseModel):
    """Schema for acknowledging an alert."""

    notes: str | None = Field(None, max_length=1000)


class AlertResolveRequest(BaseModel):
    """Schema for resolving an alert."""

    resolution_type: str = Field(..., max_length=50)
    # Types: normal_variation, false_positive, patient_contacted,
    #        care_plan_updated, referred_to_provider, other

    resolution_notes: str | None = Field(None, max_length=2000)


class AlertFilterParams(BaseModel):
    """Parameters for filtering alerts."""

    organization_id: UUID | None = None
    patient_id: UUID | None = None
    status: str | None = None  # active, acknowledged, resolved, all
    severity: str | None = None  # info, warning, critical
    category: str | None = None
    vital_type: str | None = None

    from_date: datetime | None = None
    to_date: datetime | None = None

    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
