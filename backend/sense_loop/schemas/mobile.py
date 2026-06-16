"""Mobile app schemas - iOS response formats."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Request Schemas
# =============================================================================


class SummaryRequest(BaseModel):
    """Request body for dashboard summary endpoint."""

    patient_id: str | None = None  # Optional - can be extracted from token
    days: int | None = 7
    timezone: str | None = None  # e.g., "America/Los_Angeles"


# =============================================================================
# Vitals Section
# =============================================================================

class BloodPressureSummary(BaseModel):
    """Blood pressure summary for iOS."""
    model_config = ConfigDict(populate_by_name=True)

    last_reading: datetime = Field(serialization_alias="lastReading")
    systolic: int
    diastolic: int
    status: str  # normal, elevated, high


class WeightSummary(BaseModel):
    """Weight summary for iOS."""
    model_config = ConfigDict(populate_by_name=True)

    last_reading: datetime = Field(serialization_alias="lastReading")
    value_lbs: float = Field(serialization_alias="valueLbs")
    change_from_previous: float | None = Field(None, serialization_alias="changeFromPrevious")


class TemperatureSummary(BaseModel):
    """Temperature summary for iOS."""
    model_config = ConfigDict(populate_by_name=True)

    last_reading: datetime = Field(serialization_alias="lastReading")
    value_fahrenheit: float = Field(serialization_alias="valueFahrenheit")
    status: str  # normal, elevated, high


class HeartRateSummary(BaseModel):
    """Heart rate summary for iOS."""
    model_config = ConfigDict(populate_by_name=True)

    last_reading: datetime = Field(serialization_alias="lastReading")
    value_bpm: int = Field(serialization_alias="valueBpm")
    status: str  # normal, low, high


class VitalsSummary(BaseModel):
    """Combined vitals for iOS dashboard."""
    model_config = ConfigDict(populate_by_name=True)

    blood_pressure: BloodPressureSummary | None = Field(None, serialization_alias="bloodPressure")
    weight: WeightSummary | None = None
    temperature: TemperatureSummary | None = None
    heart_rate: HeartRateSummary | None = Field(None, serialization_alias="heartRate")


# =============================================================================
# Recovery Section
# =============================================================================

class SleepTrendPoint(BaseModel):
    """Single point in sleep trend."""
    date: str  # yyyy-MM-dd
    hours: float


class SleepSummary(BaseModel):
    """Sleep summary for iOS."""
    model_config = ConfigDict(populate_by_name=True)

    last_night: datetime = Field(serialization_alias="lastNight")
    duration_minutes: int = Field(serialization_alias="durationMinutes")
    quality: str  # good, fair, poor
    trend: list[SleepTrendPoint] = []


class HRVTrendPoint(BaseModel):
    """Single point in HRV trend."""
    model_config = ConfigDict(populate_by_name=True)

    date: str  # yyyy-MM-dd
    value_ms: int = Field(serialization_alias="valueMs")


class HRVSummary(BaseModel):
    """HRV summary for iOS."""
    model_config = ConfigDict(populate_by_name=True)

    last_reading: datetime = Field(serialization_alias="lastReading")
    average_ms: int = Field(serialization_alias="averageMs")
    status: str  # healthy, fair, poor
    trend: list[HRVTrendPoint] = []


class RestingHRTrendPoint(BaseModel):
    """Single point in resting HR trend."""
    model_config = ConfigDict(populate_by_name=True)

    date: str  # yyyy-MM-dd
    value_bpm: int = Field(serialization_alias="valueBpm")


class RestingHeartRateSummary(BaseModel):
    """Resting heart rate summary for iOS."""
    model_config = ConfigDict(populate_by_name=True)

    last_reading: datetime = Field(serialization_alias="lastReading")
    value_bpm: int = Field(serialization_alias="valueBpm")
    status: str  # normal, low, high
    trend: list[RestingHRTrendPoint] | None = None


class RecoverySummary(BaseModel):
    """Recovery section for iOS dashboard."""
    model_config = ConfigDict(populate_by_name=True)

    sleep: SleepSummary | None = None
    hrv: HRVSummary | None = None
    resting_heart_rate: RestingHeartRateSummary | None = Field(None, serialization_alias="restingHeartRate")


# =============================================================================
# Activity Section
# =============================================================================

class TodayActivity(BaseModel):
    """Today's activity for iOS."""
    model_config = ConfigDict(populate_by_name=True)

    exercise_minutes: int = Field(0, serialization_alias="exerciseMinutes")
    goal_minutes: int = Field(30, serialization_alias="goalMinutes")
    progress_percent: int = Field(0, serialization_alias="progressPercent")
    low_intensity_minutes: int = Field(0, serialization_alias="lowIntensityMinutes")
    moderate_intensity_minutes: int = Field(0, serialization_alias="moderateIntensityMinutes")
    high_intensity_minutes: int = Field(0, serialization_alias="highIntensityMinutes")


class WeeklyActivityPoint(BaseModel):
    """Single day in weekly activity trend."""
    model_config = ConfigDict(populate_by_name=True)

    day_of_week: str = Field(serialization_alias="dayOfWeek")
    date: str  # yyyy-MM-dd
    exercise_minutes: int = Field(serialization_alias="exerciseMinutes")


class ActivitySummary(BaseModel):
    """Activity section for iOS dashboard."""
    model_config = ConfigDict(populate_by_name=True)

    today: TodayActivity
    weekly_trend: list[WeeklyActivityPoint] = Field(default_factory=list, serialization_alias="weeklyTrend")


# =============================================================================
# Main Response
# =============================================================================

class DashboardSummaryResponse(BaseModel):
    """Full summary response matching iOS DashboardSummaryResponse."""
    model_config = ConfigDict(populate_by_name=True)

    vitals: VitalsSummary
    recovery: RecoverySummary
    activity: ActivitySummary


# Alias for backwards compatibility
SummaryResponse = DashboardSummaryResponse


# =============================================================================
# Care Plan Section
# =============================================================================

class QuestionItem(BaseModel):
    """Question for questionnaire."""
    id: UUID
    code: str
    text: str
    help_text: str | None = None
    question_type: str
    is_required: bool = True
    options: list[dict] | None = None
    validation: dict | None = None
    condition: dict | None = None  # Conditional display logic
    order: int = 0  # Question ordering


class PendingQuestionnaire(BaseModel):
    """Pending questionnaire for patient."""
    id: UUID
    questionnaire_id: UUID
    title: str
    description: str | None = None
    due_at: datetime | None = None
    questions: list[QuestionItem] = []


class CarePlanResponse(BaseModel):
    """Care plan response for mobile."""
    patient_id: UUID
    care_plans: list[dict] = []
    medications: list[dict] = []
    activity_restrictions: list[str] = []
    warning_signs: list[str] = []
    follow_up_appointments: list[dict] = []
    emergency_contacts: list[dict] = []
    pending_questionnaires: list[PendingQuestionnaire] = []


# =============================================================================
# Questionnaire Section
# =============================================================================

class QuestionnaireAnswer(BaseModel):
    """Single answer to a questionnaire question."""
    question_id: UUID
    value_text: str | None = None
    value_number: float | None = None
    value_boolean: bool | None = None
    value_json: dict | None = None
    skipped: bool = False


class QuestionnaireSubmitRequest(BaseModel):
    """Request to submit questionnaire answers."""
    response_id: UUID
    answers: list[QuestionnaireAnswer]


class QuestionnaireSubmitResponse(BaseModel):
    """Response after submitting questionnaire."""
    success: bool
    response_id: UUID
    total_score: float | None = None
    score_interpretation: str | None = None
    message: str | None = None


# =============================================================================
# Device Registration (FCM Push Notifications)
# =============================================================================

class DeviceRegisterRequest(BaseModel):
    """Request to register a device for push notifications."""
    device_token: str = Field(..., description="FCM device token")
    platform: str = Field(default="ios", description="Device platform: ios or android")
    device_name: str | None = Field(None, description="Device name (e.g., 'iPhone 15 Pro')")
    app_version: str | None = Field(None, description="App version string")


class DeviceRegisterResponse(BaseModel):
    """Response after registering a device."""
    success: bool
    device_id: UUID
    message: str | None = None


class DeviceUnregisterRequest(BaseModel):
    """Request to unregister a device (logout/disable notifications)."""
    device_token: str
