"""Hooks for OW data events - integrates SL with OW data flow."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def on_timeseries_saved(
    db: Session,
    user_id: UUID,
    series_type: str,
    samples: list[dict[str, Any]],
    provider: str | None = None,
) -> None:
    """Hook called when OW saves timeseries data.

    This is the integration point between OW and SL.
    When wearable data arrives, we:
    1. Look up the SL Patient linked to this OW User
    2. If active patient with monitoring, run alert evaluation
    3. Update patient summary with latest values

    Args:
        db: Database session
        user_id: OW User ID
        series_type: Type of data (heart_rate, spo2, etc.)
        samples: List of data samples with timestamps and values
        provider: Data provider (whoop, oura, etc.)
    """
    from sense_loop.models import Patient

    # Find SL Patient linked to this OW User
    stmt = select(Patient).where(
        Patient.ow_user_id == user_id,
        Patient.is_active == True,  # noqa: E712
    )
    patient = db.execute(stmt).scalar_one_or_none()

    if not patient:
        # No active SL patient for this user - skip processing
        return

    if not patient.is_monitoring_active:
        # Patient not currently being monitored - skip
        return

    logger.info(
        "Processing %d %s samples for patient %s",
        len(samples),
        series_type,
        patient.id,
    )

    # Map OW series types to SL vital types
    vital_type = _map_series_to_vital(series_type)
    if not vital_type:
        # Not a vital we track - skip
        return

    # Process each sample
    for sample in samples:
        _process_sample(db, patient, vital_type, sample, provider)

    # Update patient summary with latest values
    _update_patient_summary(db, patient, vital_type, samples)


def _map_series_to_vital(series_type: str) -> str | None:
    """Map OW series type to SL vital type."""
    mapping = {
        "heart_rate": "heart_rate",
        "heart_rate_variability": "hrv",
        "heart_rate_variability_sdnn": "hrv",
        "spo2": "spo2",
        "blood_oxygen": "spo2",
        "oxygen_saturation": "spo2",  # HealthKit uses this
        "temperature": "temperature",
        "skin_temperature": "temperature",
        "body_temperature": "temperature",  # HealthKit uses this
        "respiratory_rate": "respiratory_rate",
        # Keep BP types separate for correct rule matching
        "blood_pressure_systolic": "blood_pressure_systolic",
        "blood_pressure_diastolic": "blood_pressure_diastolic",
    }
    return mapping.get(series_type)


def _process_sample(
    db: Session,
    patient: "Patient",
    vital_type: str,
    sample: dict[str, Any],
    provider: str | None,
) -> None:
    """Process a single vital sample for alert evaluation."""
    from sense_loop.services.alert_engine import AlertEngine

    value = sample.get("value")
    timestamp = sample.get("timestamp")

    if value is None:
        return

    # Parse timestamp if it's a string
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    # Run alert evaluation
    engine = AlertEngine(db)
    engine.evaluate_observation(
        patient_id=patient.id,
        vital_type=vital_type,
        value=float(value),
        observed_at=timestamp or datetime.utcnow(),
        provider=provider,
    )


def _update_patient_summary(
    db: Session,
    patient: "Patient",
    vital_type: str,
    samples: list[dict[str, Any]],
) -> None:
    """Update patient summary with latest vital values."""
    from sense_loop.services.summary_service import SummaryService

    if not samples:
        return

    # Get latest sample
    latest = max(samples, key=lambda s: s.get("timestamp", ""))
    value = latest.get("value")
    timestamp = latest.get("timestamp")

    if value is None:
        return

    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    service = SummaryService(db)
    service.update_vital(
        patient_id=patient.id,
        vital_type=vital_type,
        value=float(value),
        timestamp=timestamp or datetime.utcnow(),
    )
