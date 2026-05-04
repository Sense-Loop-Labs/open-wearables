"""HR Anomaly Service for storing and dispatching anomalies.

SENSE-LOOP ADDITION: This entire module is a Sense Loop addition for clinical HR alerting.

Handles:
- Recording anomalies to the database
- Calculating deviation from baseline
- Dispatching to Medplum for clinical review
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.hr_analysis import HRAnomaly, HRBaseline
from app.services.medplum.hr_processor import SustainedAnomaly
from app.services.medplum.webhook import medplum_webhook

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
        """Store anomaly in database and dispatch to Medplum.

        Args:
            user_id: The user's UUID
            anomaly: The detected sustained anomaly
            context_data: Supporting context (minutes_since_workout, recent_steps, recent_energy)
            medplum_patient_id: Optional Medplum Patient ID for FHIR integration

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

        # Dispatch to Medplum immediately
        if medplum_webhook.is_enabled() and medplum_patient_id:
            success = self._dispatch_to_medplum(record, medplum_patient_id)
            if success:
                record.sent_to_medplum_at = datetime.now(timezone.utc)
                self.db.commit()

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

    def _dispatch_to_medplum(self, record: HRAnomaly, medplum_patient_id: str) -> bool:
        """Send anomaly to Medplum for clinical review."""
        payload = {
            "event_type": "hr.anomaly",
            "user_id": str(record.user_id),
            "medplum_patient_id": medplum_patient_id,
            "timestamp": record.detected_at.isoformat(),
            "data": {
                "heart_rate": record.heart_rate,
                "context": record.context,
                "reason": record.reason,
                "severity": record.severity,
                "baseline_resting_hr": record.baseline_resting_hr,
                "deviation_percent": float(record.deviation_percent) if record.deviation_percent else None,
                "minutes_since_workout": record.minutes_since_workout,
                "recent_step_count": record.recent_step_count,
                "recent_active_energy": float(record.recent_active_energy) if record.recent_active_energy else None,
            },
        }

        try:
            success = medplum_webhook.send_sync(payload)
            if success:
                logger.info("Sent HR anomaly to Medplum: %s", record.id)
            else:
                logger.error("Failed to send HR anomaly to Medplum: %s", record.id)
            return success
        except Exception as e:
            logger.error("Error sending HR anomaly to Medplum: %s", e, exc_info=True)
            return False

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
