"""Summary service - patient summary updates."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from sense_loop.models import Alert, Patient, PatientSummary

logger = logging.getLogger(__name__)


class SummaryService:
    """Service for updating patient summaries."""

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_summary(self, patient_id: UUID) -> PatientSummary:
        """Get or create a patient summary."""
        stmt = select(PatientSummary).where(PatientSummary.patient_id == patient_id)
        summary = self.db.execute(stmt).scalar_one_or_none()

        if not summary:
            summary = PatientSummary(
                id=uuid4(),
                patient_id=patient_id,
            )
            self.db.add(summary)
            self.db.flush()

        return summary

    def update_vital(
        self,
        patient_id: UUID,
        vital_type: str,
        value: float,
        timestamp: datetime,
    ) -> PatientSummary:
        """Update a specific vital in the patient summary."""
        summary = self.get_or_create_summary(patient_id)

        # Update the appropriate vital field
        # Map series type codes to summary fields
        vital_map = {
            "heart_rate": ("latest_heart_rate", "latest_heart_rate_at"),
            "spo2": ("latest_spo2", "latest_spo2_at"),
            "oxygen_saturation": ("latest_spo2", "latest_spo2_at"),  # HealthKit code
            "temperature": ("latest_temperature", "latest_temperature_at"),
            "body_temperature": ("latest_temperature", "latest_temperature_at"),  # HealthKit code
            "hrv": ("latest_hrv", "latest_hrv_at"),
            "heart_rate_variability": ("latest_hrv", "latest_hrv_at"),  # HealthKit code
            "respiratory_rate": ("latest_respiratory_rate", "latest_respiratory_rate_at"),
            "blood_pressure_systolic": ("latest_blood_pressure_systolic", "latest_blood_pressure_at"),
            "blood_pressure_diastolic": ("latest_blood_pressure_diastolic", "latest_blood_pressure_at"),
        }

        if vital_type in vital_map:
            value_field, timestamp_field = vital_map[vital_type]

            # Only update if newer
            current_timestamp = getattr(summary, timestamp_field)
            if current_timestamp is None or timestamp > current_timestamp:
                setattr(summary, value_field, value)
                setattr(summary, timestamp_field, timestamp)

        # Update data freshness
        if summary.last_data_received_at is None or timestamp > summary.last_data_received_at:
            summary.last_data_received_at = timestamp

        summary.updated_at = datetime.utcnow()
        self.db.flush()

        return summary

    def update_activity(
        self,
        patient_id: UUID,
        steps: int | None = None,
        active_calories: float | None = None,
        distance_meters: float | None = None,
        active_minutes: int | None = None,
    ) -> PatientSummary:
        """Update today's activity stats."""
        summary = self.get_or_create_summary(patient_id)

        if steps is not None:
            summary.today_steps = steps
        if active_calories is not None:
            summary.today_active_calories = active_calories
        if distance_meters is not None:
            summary.today_distance_meters = distance_meters
        if active_minutes is not None:
            summary.today_active_minutes = active_minutes

        summary.updated_at = datetime.utcnow()
        self.db.flush()

        return summary

    def update_sleep(
        self,
        patient_id: UUID,
        duration_minutes: int,
        score: float | None = None,
        sleep_date: datetime | None = None,
    ) -> PatientSummary:
        """Update last night's sleep data."""
        summary = self.get_or_create_summary(patient_id)

        summary.last_sleep_duration_minutes = duration_minutes
        summary.last_sleep_score = score
        summary.last_sleep_date = sleep_date or datetime.utcnow()

        summary.updated_at = datetime.utcnow()
        self.db.flush()

        return summary

    def update_recovery(
        self,
        patient_id: UUID,
        recovery_score: float | None = None,
        readiness_score: float | None = None,
        timestamp: datetime | None = None,
    ) -> PatientSummary:
        """Update recovery/readiness scores."""
        summary = self.get_or_create_summary(patient_id)
        ts = timestamp or datetime.utcnow()

        if recovery_score is not None:
            summary.latest_recovery_score = recovery_score
            summary.latest_recovery_score_at = ts

        if readiness_score is not None:
            summary.latest_readiness_score = readiness_score
            summary.latest_readiness_score_at = ts

        summary.updated_at = datetime.utcnow()
        self.db.flush()

        return summary

    def update_alert_counts(self, patient_id: UUID) -> PatientSummary:
        """Recalculate alert counts from database."""
        from sqlalchemy import func

        summary = self.get_or_create_summary(patient_id)

        # Count active alerts
        active_count = self.db.execute(
            select(func.count())
            .select_from(Alert)
            .where(
                Alert.patient_id == patient_id,
                Alert.status == "active",
            )
        ).scalar() or 0

        # Count critical alerts
        critical_count = self.db.execute(
            select(func.count())
            .select_from(Alert)
            .where(
                Alert.patient_id == patient_id,
                Alert.status == "active",
                Alert.severity == "critical",
            )
        ).scalar() or 0

        # Get last alert time
        last_alert = self.db.execute(
            select(Alert.triggered_at)
            .where(Alert.patient_id == patient_id)
            .order_by(Alert.triggered_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        summary.active_alerts_count = active_count
        summary.active_critical_alerts_count = critical_count
        summary.last_alert_at = last_alert

        # Update overall status
        if critical_count > 0:
            summary.overall_status = "critical"
        elif active_count > 0:
            summary.overall_status = "warning"
        elif summary.last_data_received_at is None:
            summary.overall_status = "no_data"
        else:
            summary.overall_status = "good"

        summary.updated_at = datetime.utcnow()
        self.db.flush()

        return summary

    def refresh_summary(self, patient_id: UUID) -> PatientSummary:
        """Full refresh of patient summary from database.

        This is more expensive but ensures data consistency.
        Use for periodic sync or when data might be out of sync.
        """
        summary = self.get_or_create_summary(patient_id)

        # Update alert counts
        self.update_alert_counts(patient_id)

        # TODO: Query OW DataPointSeries for latest vitals
        # This would involve querying the OW tables directly

        summary.last_sync_at = datetime.utcnow()
        summary.updated_at = datetime.utcnow()
        self.db.flush()

        return summary
