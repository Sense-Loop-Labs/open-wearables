"""Patient summary model - pre-computed vitals for O(1) dashboard queries."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, Unique


class PatientSummary(BaseDbModel):
    """Pre-computed patient vitals summary for fast dashboard queries.

    Updated asynchronously when new data arrives.
    Provides O(1) query time for patient dashboard.
    """

    __tablename__ = "sl_patient_summary"

    id: Mapped[PrimaryKey[UUID]]

    patient_id: Mapped[Unique[UUID]] = mapped_column(
        ForeignKey("sl_patient.id", ondelete="CASCADE"),
        index=True,
    )

    # Latest vitals
    latest_heart_rate: Mapped[float | None] = mapped_column(nullable=True)
    latest_heart_rate_at: Mapped[datetime | None] = mapped_column(nullable=True)

    latest_spo2: Mapped[float | None] = mapped_column(nullable=True)
    latest_spo2_at: Mapped[datetime | None] = mapped_column(nullable=True)

    latest_temperature: Mapped[float | None] = mapped_column(nullable=True)
    latest_temperature_at: Mapped[datetime | None] = mapped_column(nullable=True)

    latest_blood_pressure_systolic: Mapped[float | None] = mapped_column(nullable=True)
    latest_blood_pressure_diastolic: Mapped[float | None] = mapped_column(nullable=True)
    latest_blood_pressure_at: Mapped[datetime | None] = mapped_column(nullable=True)

    latest_hrv: Mapped[float | None] = mapped_column(nullable=True)
    latest_hrv_at: Mapped[datetime | None] = mapped_column(nullable=True)

    latest_respiratory_rate: Mapped[float | None] = mapped_column(nullable=True)
    latest_respiratory_rate_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Daily aggregates (today)
    today_steps: Mapped[int | None] = mapped_column(nullable=True)
    today_active_calories: Mapped[float | None] = mapped_column(nullable=True)
    today_distance_meters: Mapped[float | None] = mapped_column(nullable=True)
    today_active_minutes: Mapped[int | None] = mapped_column(nullable=True)

    # Sleep (last night)
    last_sleep_duration_minutes: Mapped[int | None] = mapped_column(nullable=True)
    last_sleep_score: Mapped[float | None] = mapped_column(nullable=True)
    last_sleep_date: Mapped[datetime | None] = mapped_column(nullable=True)

    # Recovery/Readiness
    latest_recovery_score: Mapped[float | None] = mapped_column(nullable=True)
    latest_recovery_score_at: Mapped[datetime | None] = mapped_column(nullable=True)
    latest_readiness_score: Mapped[float | None] = mapped_column(nullable=True)
    latest_readiness_score_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Trends (computed over last 7 days)
    heart_rate_trend: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # {"direction": "increasing", "change_percent": 5.2, "values": [72, 74, 75, ...]}

    spo2_trend: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sleep_trend: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    activity_trend: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Alert summary
    active_alerts_count: Mapped[int] = mapped_column(default=0)
    active_critical_alerts_count: Mapped[int] = mapped_column(default=0)
    last_alert_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Questionnaire status
    pending_questionnaires_count: Mapped[int] = mapped_column(default=0)
    last_questionnaire_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Questionnaire concerns (from latest response)
    has_questionnaire_concerns: Mapped[bool] = mapped_column(default=False)
    questionnaire_concern_count: Mapped[int] = mapped_column(default=0)
    highest_questionnaire_severity: Mapped[str | None] = mapped_column(nullable=True)
    # Severities: None, 'warning', 'critical'
    questionnaire_concerns: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # List of {question_text, answer_text, severity, question_code}
    last_questionnaire_response_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Data freshness
    last_data_received_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Overall status
    overall_status: Mapped[str | None] = mapped_column(nullable=True)
    # Statuses: good, warning, critical, no_data

    # Update tracking
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient: Mapped["Patient"] = relationship(back_populates="summary")

    @property
    def is_data_stale(self) -> bool:
        """Check if data is more than 24 hours old."""
        if not self.last_data_received_at:
            return True
        return (datetime.utcnow() - self.last_data_received_at).total_seconds() > 86400

    @property
    def has_critical_status(self) -> bool:
        """Check if patient has any critical indicators."""
        return self.active_critical_alerts_count > 0 or self.overall_status == "critical"
