"""HR Anomaly Service for storing and dispatching anomalies.

SENSE-LOOP ADDITION: This entire module is a Sense Loop addition for clinical HR alerting.

Handles:
- Recording anomalies to the database
- Calculating deviation from baseline
- Creating Sense Loop alerts for clinical review
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.hr_analysis import HRAnomaly, HRBaseline
from app.services.medplum.hr_processor import SustainedAnomaly

logger = logging.getLogger(__name__)


class HRAnomalyService:
    """Handles storing and dispatching HR anomalies."""

    def __init__(self, db: Session):
        self.db = db

    def record_anomaly(
        self,
        user_id: UUID,
        anomaly: SustainedAnomaly,
        context_data: dict[str, Any],
        medplum_patient_id: str | None = None,
    ) -> HRAnomaly:
        """Store anomaly in database and create Sense Loop alert.

        Args:
            user_id: The user's UUID (OW user_id)
            anomaly: The detected sustained anomaly
            context_data: Supporting context (minutes_since_workout, recent_steps, recent_energy)
            medplum_patient_id: Deprecated - no longer used

        Returns:
            The created HRAnomaly database record
        """
        # Get baseline for comparison
        baseline = self._get_baseline(user_id)

        # Calculate severity based on max HR and baseline
        severity = self._calculate_severity(anomaly.max_hr, baseline)

        # Calculate deviation percentage
        deviation_percent = None
        if baseline and baseline.resting_hr_avg:
            deviation_percent = Decimal(str(
                ((anomaly.avg_hr - float(baseline.resting_hr_avg)) / float(baseline.resting_hr_avg)) * 100
            ))

        # Create the anomaly record
        record = HRAnomaly(
            user_id=user_id,
            detected_at=datetime.now(timezone.utc),
            heart_rate=int(anomaly.max_hr),
            context="resting",  # Sustained anomalies are only detected in resting context
            reason=anomaly.reason,
            severity=severity,
            baseline_resting_hr=int(baseline.resting_hr_avg) if baseline and baseline.resting_hr_avg else None,
            deviation_percent=deviation_percent,
            minutes_since_workout=context_data.get("minutes_since_workout"),
            recent_step_count=context_data.get("recent_steps"),
            recent_active_energy=Decimal(str(context_data.get("recent_energy", 0))) if context_data.get("recent_energy") else None,
        )

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        logger.info(
            "Recorded HR anomaly for user %s: %d bpm, severity=%s, reason=%s",
            user_id,
            anomaly.max_hr,
            severity,
            anomaly.reason,
        )

        # Create Sense Loop alert
        self._create_sl_alert(user_id, record, anomaly, context_data)

        return record

    def _get_baseline(self, user_id: UUID) -> HRBaseline | None:
        """Get the user's HR baseline if available."""
        return self.db.query(HRBaseline).filter(
            HRBaseline.user_id == user_id
        ).first()

    def _calculate_severity(self, max_hr: int, baseline: HRBaseline | None) -> str:
        """Calculate severity based on HR value and baseline.

        High severity if:
        - HR > 120 bpm, OR
        - HR > elevated_threshold from baseline, OR
        - HR > baseline avg + 30 bpm

        Medium severity otherwise.
        """
        if max_hr > 120:
            return "high"

        if baseline:
            if baseline.elevated_threshold and max_hr > baseline.elevated_threshold:
                return "high"
            if baseline.resting_hr_avg and max_hr > float(baseline.resting_hr_avg) + 30:
                return "high"

        return "medium"

    def _create_sl_alert(
        self,
        user_id: UUID,
        record: HRAnomaly,
        anomaly: SustainedAnomaly,
        context_data: dict[str, Any],
    ) -> None:
        """Create a Sense Loop alert for the HR anomaly.

        This replaces the previous Medplum dispatch. Alerts are created directly
        in the Sense Loop database for clinical review.
        """
        from sense_loop.models import Alert, Patient
        from sense_loop.services.summary_service import SummaryService

        # Find the SL Patient linked to this OW User
        stmt = select(Patient).where(
            Patient.ow_user_id == user_id,
            Patient.is_active == True,  # noqa: E712
        )
        patient = self.db.execute(stmt).scalar_one_or_none()

        if not patient:
            logger.warning(
                "No active SL patient found for user %s - skipping alert creation",
                user_id,
            )
            return

        # Map severity: hr_anomaly_service uses "high"/"medium", SL uses "critical"/"warning"
        sl_severity = "critical" if record.severity == "high" else "warning"

        # Build alert title based on reason
        if "elevated" in anomaly.reason or "high" in anomaly.reason.lower():
            title = "High Heart Rate Alert"
            message = (
                f"Patient's heart rate of {record.heart_rate} bpm has been elevated "
                f"for a sustained period while at rest."
            )
        elif "low" in anomaly.reason.lower():
            title = "Low Heart Rate Alert"
            message = (
                f"Patient's heart rate of {record.heart_rate} bpm has been low "
                f"for a sustained period."
            )
        else:
            title = "Heart Rate Anomaly Alert"
            message = f"Sustained heart rate anomaly detected: {record.heart_rate} bpm. Reason: {anomaly.reason}"

        # Add context to message
        if record.baseline_resting_hr:
            message += f" Baseline resting HR: {record.baseline_resting_hr} bpm."
        if record.deviation_percent:
            message += f" Deviation: {record.deviation_percent:.1f}%."
        if context_data.get("minutes_since_workout"):
            message += f" Minutes since last workout: {context_data['minutes_since_workout']}."

        # Create the alert
        alert = Alert(
            id=uuid4(),
            patient_id=patient.id,
            organization_id=patient.organization_id,
            title=title,
            message=message,
            severity=sl_severity,
            category="vital_sign",
            status="active",
            triggered_at=record.detected_at,
            days_post_surgery=patient.days_post_surgery,
            patient_context="resting",  # Sustained anomalies only fire in resting context
            vital_type="heart_rate",
            observed_value=float(record.heart_rate),
            threshold_breached="high_warning" if "elevated" in anomaly.reason else "low_warning",
            data={
                "anomaly_id": str(record.id),
                "reason": anomaly.reason,
                "baseline_resting_hr": record.baseline_resting_hr,
                "deviation_percent": float(record.deviation_percent) if record.deviation_percent else None,
                "minutes_since_workout": context_data.get("minutes_since_workout"),
                "recent_steps": context_data.get("recent_steps"),
                "recent_energy": float(context_data.get("recent_energy", 0)) if context_data.get("recent_energy") else None,
                "reading_count": anomaly.reading_count,
                "avg_hr": anomaly.avg_hr,
                "activity_aware": True,  # Flag that this used activity-aware detection
            },
        )

        self.db.add(alert)
        self.db.flush()

        logger.info(
            "Created SL alert %s for patient %s: %s (%d bpm)",
            alert.id,
            patient.id,
            title,
            record.heart_rate,
        )

        # Update patient summary alert counts
        summary_service = SummaryService(self.db)
        summary_service.update_alert_counts(patient.id)

    def update_medplum_ids(
        self,
        anomaly_id: UUID,
        observation_id: str | None = None,
        flag_id: str | None = None,
    ) -> None:
        """Update the Medplum resource IDs on an anomaly record."""
        record = self.db.query(HRAnomaly).filter(HRAnomaly.id == anomaly_id).first()
        if record:
            if observation_id:
                record.medplum_observation_id = observation_id
            if flag_id:
                record.medplum_flag_id = flag_id
            self.db.commit()
