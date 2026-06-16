"""Questionnaire template schemas for API request/response validation."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Question Option Schemas
# =============================================================================


class QuestionOptionSchema(BaseModel):
    """A single option for choice questions."""

    value: str
    label: str
    score: float | None = None


class QuestionAlertConfig(BaseModel):
    """Alert configuration for a question."""

    trigger_values: list[str] = Field(default_factory=list)
    alert_severity: str = "warning"  # Default severity (info, warning, critical)
    alert_message: str | None = None
    # Per-value severity overrides: {"Poor": "warning", "Very Poor": "critical"}
    severity_by_value: dict[str, str] | None = None
    # Flag any answer (for optional text/number fields)
    alert_on_any_value: bool = False


class QuestionValidation(BaseModel):
    """Validation rules for a question."""

    min: float | None = None
    max: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None


class QuestionCondition(BaseModel):
    """Condition for showing a question."""

    question_code: str
    operator: str  # equals, not_equals, greater_than, less_than, contains
    value: Any


# =============================================================================
# Question Schemas
# =============================================================================


class QuestionCreate(BaseModel):
    """Create a questionnaire question."""

    code: str = Field(..., min_length=1, max_length=100)
    text: str = Field(..., min_length=1)
    help_text: str | None = None
    question_type: str = Field(..., max_length=50)  # boolean, single_choice, multi_choice, text, number, scale
    order: int = 0
    is_required: bool = True
    validation: QuestionValidation | None = None
    options: list[QuestionOptionSchema] | None = None
    condition: QuestionCondition | None = None
    score_weight: float | None = None
    alert_config: QuestionAlertConfig | None = None


class QuestionUpdate(BaseModel):
    """Update a questionnaire question."""

    code: str | None = None
    text: str | None = None
    help_text: str | None = None
    question_type: str | None = None
    order: int | None = None
    is_required: bool | None = None
    validation: QuestionValidation | None = None
    options: list[QuestionOptionSchema] | None = None
    condition: QuestionCondition | None = None
    score_weight: float | None = None
    alert_config: QuestionAlertConfig | None = None
    is_active: bool | None = None


class QuestionResponse(BaseModel):
    """Questionnaire question response."""

    id: UUID
    questionnaire_id: UUID
    code: str
    text: str
    help_text: str | None
    question_type: str
    order: int
    is_required: bool
    validation: dict | None
    options: list[dict] | None
    condition: dict | None
    score_weight: float | None
    alert_config: dict | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


# =============================================================================
# Questionnaire Schemas
# =============================================================================


class ScoringRange(BaseModel):
    """A scoring range for interpretation."""

    min: float
    max: float
    label: str
    severity: str = "info"  # info, warning, critical


class ScoringConfig(BaseModel):
    """Scoring configuration for a questionnaire."""

    method: str = "sum"  # sum, average, weighted
    ranges: list[ScoringRange] = Field(default_factory=list)


class QuestionnaireCreate(BaseModel):
    """Create a questionnaire template."""

    title: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    organization_id: UUID | None = None
    questionnaire_type: str = Field(default="on_demand", max_length=50)  # daily, weekly, on_demand, triggered
    category: str = Field(default="symptom", max_length=50)  # symptom, pain, mood, activity, medication
    estimated_minutes: int | None = None
    allow_skip: bool = False
    require_completion: bool = True
    has_scoring: bool = False
    scoring_config: ScoringConfig | None = None
    questions: list[QuestionCreate] | None = None


class QuestionnaireUpdate(BaseModel):
    """Update a questionnaire template."""

    title: str | None = None
    code: str | None = None
    description: str | None = None
    questionnaire_type: str | None = None
    category: str | None = None
    estimated_minutes: int | None = None
    allow_skip: bool | None = None
    require_completion: bool | None = None
    has_scoring: bool | None = None
    scoring_config: ScoringConfig | None = None
    is_active: bool | None = None


class QuestionnaireResponse(BaseModel):
    """Questionnaire template response."""

    id: UUID
    organization_id: UUID | None
    title: str
    code: str
    description: str | None
    questionnaire_type: str
    category: str
    estimated_minutes: int | None
    allow_skip: bool
    require_completion: bool
    has_scoring: bool
    scoring_config: dict | None
    is_active: bool
    version: int
    question_count: int = 0
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class QuestionnaireDetailResponse(QuestionnaireResponse):
    """Questionnaire with questions included."""

    questions: list[QuestionResponse] = Field(default_factory=list)


class QuestionnaireListResponse(BaseModel):
    """List of questionnaire templates."""

    items: list[QuestionnaireResponse]
    total: int


# =============================================================================
# Question Reorder Schema
# =============================================================================


class QuestionReorderItem(BaseModel):
    """A single question reorder item."""

    question_id: UUID
    order: int


class QuestionReorderRequest(BaseModel):
    """Request to reorder questions."""

    questions: list[QuestionReorderItem]


# =============================================================================
# Patient Questionnaire Assignment Schemas
# =============================================================================


class QuestionnaireAssignRequest(BaseModel):
    """Request to assign a questionnaire to a patient."""

    questionnaire_id: UUID


class PatientQuestionnaireResponse(BaseModel):
    """Response for a patient's questionnaire assignment."""

    id: UUID
    patient_id: UUID
    questionnaire_id: UUID
    questionnaire_title: str
    status: str
    created_at: datetime
    due_at: datetime | None = None

    class Config:
        from_attributes = True


class PatientQuestionnaireListResponse(BaseModel):
    """List of questionnaire assignments for a patient."""

    items: list[PatientQuestionnaireResponse]
    total: int


# =============================================================================
# Response Detail Schemas (with answers)
# =============================================================================


class QuestionnaireAnswerResponse(BaseModel):
    """A single answer to a questionnaire question."""

    id: UUID
    question_id: UUID
    question_code: str
    question_text: str
    question_type: str
    question_help_text: str | None = None
    question_options: list[QuestionOptionSchema] | None = None
    question_is_required: bool = False
    question_order: int = 0
    value_text: str | None = None
    value_number: float | None = None
    value_boolean: bool | None = None
    value_json: dict | None = None
    skipped: bool = False
    score: float | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class QuestionnaireResponseDetail(BaseModel):
    """Detailed questionnaire response with answers."""

    id: UUID
    patient_id: UUID
    questionnaire_id: UUID
    questionnaire_title: str
    questionnaire_description: str | None = None
    status: str
    total_score: float | None = None
    score_interpretation: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    due_at: datetime | None = None
    answers: list[QuestionnaireAnswerResponse]

    class Config:
        from_attributes = True
