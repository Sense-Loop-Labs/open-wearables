"""Patient schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class PatientBase(BaseModel):
    """Base patient fields."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date
    gender: str | None = Field(None, max_length=50)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    address: str | None = None

    mrn: str | None = Field(None, max_length=50)
    primary_diagnosis: str | None = Field(None, max_length=255)
    surgery_type_code: str | None = Field(None, max_length=100)  # SNOMED code
    surgery_date: date | None = None
    discharge_date: date | None = None


class PatientCreate(PatientBase):
    """Schema for creating a patient."""

    organization_id: UUID
    alert_protocol_id: UUID | None = None
    monitoring_start_date: date | None = None
    monitoring_end_date: date | None = None


class PatientUpdate(BaseModel):
    """Schema for updating a patient."""

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    date_of_birth: date | None = None
    gender: str | None = Field(None, max_length=50)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    address: str | None = None

    mrn: str | None = Field(None, max_length=50)
    primary_diagnosis: str | None = Field(None, max_length=255)
    surgery_type_code: str | None = Field(None, max_length=100)
    surgery_date: date | None = None
    discharge_date: date | None = None

    alert_protocol_id: UUID | None = None
    monitoring_start_date: date | None = None
    monitoring_end_date: date | None = None
    custom_thresholds: dict | None = None
    is_active: bool | None = None


class PatientSummaryResponse(BaseModel):
    """Embedded summary for patient response."""

    latest_heart_rate: float | None = None
    latest_heart_rate_at: datetime | None = None
    latest_spo2: float | None = None
    latest_spo2_at: datetime | None = None
    latest_temperature: float | None = None
    latest_temperature_at: datetime | None = None
    latest_hrv: float | None = None
    latest_hrv_at: datetime | None = None
    latest_respiratory_rate: float | None = None
    latest_respiratory_rate_at: datetime | None = None
    latest_blood_pressure_systolic: float | None = None
    latest_blood_pressure_diastolic: float | None = None
    latest_blood_pressure_at: datetime | None = None
    today_steps: int | None = None
    today_active_minutes: int | None = None
    last_sleep_duration_minutes: int | None = None
    active_alerts_count: int = 0
    active_critical_alerts_count: int = 0
    overall_status: str | None = None
    last_data_received_at: datetime | None = None

    # Questionnaire concerns
    has_questionnaire_concerns: bool = False
    questionnaire_concern_count: int = 0
    highest_questionnaire_severity: str | None = None
    questionnaire_concerns: list[dict] | None = None
    last_questionnaire_response_at: datetime | None = None


class PatientResponse(BaseModel):
    """Schema for patient response."""

    id: UUID
    organization_id: UUID
    ow_user_id: UUID | None = None

    first_name: str
    last_name: str
    full_name: str
    date_of_birth: date
    age: int | None = None
    gender: str | None = None
    email: str | None = None
    phone: str | None = None

    mrn: str | None = None
    primary_diagnosis: str | None = None
    surgery_type_code: str | None = None
    surgery_date: date | None = None
    discharge_date: date | None = None
    days_post_surgery: int | None = None

    enrollment_status: str
    enrolled_at: datetime | None = None
    activation_code: str | None = None
    activation_code_expires_at: datetime | None = None

    monitoring_start_date: date | None = None
    monitoring_end_date: date | None = None
    is_monitoring_active: bool = False

    alert_protocol_id: UUID | None = None
    is_active: bool

    created_at: datetime
    summary: PatientSummaryResponse | None = None

    class Config:
        from_attributes = True


class PatientListResponse(BaseModel):
    """Schema for paginated patient list."""

    items: list[PatientResponse]
    total: int
    page: int
    page_size: int
    pages: int


class VitalReading(BaseModel):
    """A single vital reading."""

    vital_type: str
    value: float
    value_secondary: float | None = None  # For BP diastolic
    unit: str
    recorded_at: datetime
    source: str | None = None
    is_aggregated: bool = False  # True for hourly HR averages


class VitalsHistoryResponse(BaseModel):
    """Historical vitals response with pagination."""

    items: list[VitalReading]
    total: int
    page: int
    page_size: int
    pages: int
    vital_type: str | None = None  # Filter applied, None = all
