"""Instruction template schemas for API request/response validation."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Activity Template Schemas
# =============================================================================


class ActivityTemplateCreate(BaseModel):
    """Create an activity template."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str
    category_code: str = Field(..., max_length=50)
    organization_id: UUID | None = None
    kind: str = Field(default="task", max_length=50)
    completion_method: str = Field(default="manual", max_length=50)
    data_trigger_types: list[str] | None = None
    data_threshold: dict | None = None
    confirmation_prompt: str | None = None
    content: dict | None = None
    default_timing: dict | None = None
    code_system: str | None = None
    code_value: str | None = None


class ActivityTemplateUpdate(BaseModel):
    """Update an activity template."""

    title: str | None = None
    description: str | None = None
    category_code: str | None = None
    kind: str | None = None
    completion_method: str | None = None
    data_trigger_types: list[str] | None = None
    data_threshold: dict | None = None
    confirmation_prompt: str | None = None
    content: dict | None = None
    default_timing: dict | None = None
    code_system: str | None = None
    code_value: str | None = None
    status: str | None = None


class ActivityTemplateResponse(BaseModel):
    """Activity template response."""

    id: UUID
    organization_id: UUID | None
    name: str
    title: str
    description: str
    status: str
    version: str
    category_code: str
    kind: str
    completion_method: str
    data_trigger_types: list[str] | None
    data_threshold: dict | None
    confirmation_prompt: str | None
    content: dict
    default_timing: dict | None
    code_system: str | None
    code_value: str | None
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class ActivityTemplateListResponse(BaseModel):
    """List of activity templates."""

    items: list[ActivityTemplateResponse]
    total: int


# =============================================================================
# Instruction Template Schemas
# =============================================================================


class InstructionTemplateCreate(BaseModel):
    """Create an instruction template."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str
    organization_id: UUID | None = None
    content: dict | None = None
    health_focus_codes: list[str] | None = None
    notification_config: dict | None = None


class InstructionTemplateUpdate(BaseModel):
    """Update an instruction template."""

    title: str | None = None
    description: str | None = None
    content: dict | None = None
    health_focus_codes: list[str] | None = None
    notification_config: dict | None = None
    status: str | None = None
    version: str | None = None


class InstructionTemplateResponse(BaseModel):
    """Instruction template response."""

    id: UUID
    organization_id: UUID | None
    name: str
    title: str
    description: str
    status: str
    version: str
    content: dict
    health_focus_codes: list[str]
    notification_config: dict | None
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class InstructionTemplateListResponse(BaseModel):
    """List of instruction templates."""

    items: list[InstructionTemplateResponse]
    total: int


class InstructionTemplatePreview(BaseModel):
    """Preview of instruction template with resolved activities."""

    id: str
    name: str
    title: str
    description: str
    version: str
    status: str
    health_focus_codes: list[str]
    content: dict
    notification_config: dict | None


# =============================================================================
# Patient Instruction Plan Schemas
# =============================================================================


class PatientPlanAssign(BaseModel):
    """Assign a plan to a patient."""

    template_id: UUID
    effective_start: datetime | None = None
    effective_end: datetime | None = None
    customizations: dict | None = None
    reference_date: date | None = None
    reference_type: str | None = None
    generate_tasks: bool = True


class PatientPlanUpdate(BaseModel):
    """Update a patient instruction plan."""

    customizations: dict | None = None
    effective_end: datetime | None = None
    regenerate_tasks: bool = True


class PatientPlanResponse(BaseModel):
    """Patient instruction plan response."""

    id: UUID
    patient_id: UUID
    template_id: UUID
    template_name: str | None = None
    template_title: str | None = None
    status: str
    effective_start: datetime
    effective_end: datetime | None
    customizations: dict | None
    reference_date: date | None
    reference_type: str | None
    tasks_generated_through: date | None
    assigned_by_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PatientPlanListResponse(BaseModel):
    """List of patient instruction plans."""

    items: list[PatientPlanResponse]
    total: int


class PatientPlanContent(BaseModel):
    """Patient plan with fully resolved content."""

    id: UUID
    patient_id: UUID
    template_title: str
    status: str
    effective_start: datetime
    effective_end: datetime | None
    content: dict


# =============================================================================
# Patient Instruction Task Schemas
# =============================================================================


class TaskResponse(BaseModel):
    """Task response for mobile app."""

    id: UUID
    plan_id: UUID
    task_type: str
    task_code: str
    title: str
    description: str | None
    completion_method: str
    status: str
    scheduled_date: date
    scheduled_at: datetime
    scheduled_time_local: str | None
    time_window_minutes: int
    confirmation_prompt: str | None
    completed_at: datetime | None
    completion_source: str | None
    linked_data_value: str | None
    user_notes: str | None
    snoozed_until: datetime | None
    snooze_count: int

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """List of tasks."""

    items: list[TaskResponse]
    total: int
    pending_count: int
    completed_count: int


class TaskCompleteRequest(BaseModel):
    """Request to complete a task manually."""

    notes: str | None = None


class TaskSkipRequest(BaseModel):
    """Request to skip a task."""

    reason: str | None = None


class TaskSnoozeRequest(BaseModel):
    """Request to snooze a task."""

    snooze_minutes: int = Field(default=30, ge=5, le=240)


class TaskConfirmationResponse(BaseModel):
    """Response to a task confirmation notification."""

    response: str = Field(..., pattern="^(yes|no|snooze)$")
    notes: str | None = None


class TaskActionResponse(BaseModel):
    """Response for task action endpoints."""

    success: bool
    task_id: UUID
    new_status: str
    message: str


# =============================================================================
# Mobile API Task Schemas
# =============================================================================


class DailyTasksResponse(BaseModel):
    """Daily tasks for mobile app."""

    date: date
    tasks: list[TaskResponse]
    total: int
    pending: int
    completed: int
    missed: int
