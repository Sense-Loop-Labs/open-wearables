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
    4. Trigger task auto-completion check

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

    # Check if it's activity data
    is_activity = _is_activity_series(series_type)

    if not vital_type and not is_activity:
        # Not a vital or activity we track - skip
        return

    if vital_type:
        # Process each sample for vitals
        for sample in samples:
            _process_sample(db, patient, vital_type, sample, provider)

        # Update patient summary with latest vital values
        _update_patient_summary(db, patient, vital_type, samples)

        # Trigger task auto-completion check (async via Celery)
        _trigger_task_completion(patient.id, vital_type, samples)

    if is_activity:
        # Update patient activity summary
        _update_activity_summary(db, patient, series_type, samples)


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


def _is_activity_series(series_type: str) -> bool:
    """Check if series type is activity-related."""
    activity_types = {
        "steps",
        "active_energy",
        "active_energy_burned",  # HealthKit
        "basal_energy_burned",   # HealthKit
        "distance_walking_running",  # HealthKit
        "distance",
        "flights_climbed",
        "exercise_time",         # HealthKit exercise minutes
        "apple_exercise_time",   # Apple Watch exercise ring
    }
    return series_type in activity_types


def _process_sample(
    db: Session,
    patient: "Patient",
    vital_type: str,
    sample: dict[str, Any],
    provider: str | None,
) -> None:
    """Process a single vital sample for alert evaluation."""
    from sense_loop.services.alert_engine import AlertAction, AlertEngine
    from sense_loop.services.summary_service import SummaryService

    # Skip heart rate - it uses activity-aware analysis in hr_anomaly_service instead
    # This prevents duplicate alerts from individual readings without activity context
    if vital_type == "heart_rate":
        return

    value = sample.get("value")
    timestamp = sample.get("timestamp")

    if value is None:
        return

    # Parse timestamp if it's a string
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    # Run alert evaluation
    engine = AlertEngine(db)
    result = engine.evaluate_observation(
        patient_id=patient.id,
        vital_type=vital_type,
        value=float(value),
        observed_at=timestamp or datetime.utcnow(),
        provider=provider,
    )

    # Update patient summary alert counts if an alert was created, updated, or resolved
    if result.action in (AlertAction.CREATED, AlertAction.UPDATED, AlertAction.RESOLVED):
        summary_service = SummaryService(db)
        summary_service.update_alert_counts(patient.id)


def _update_activity_summary(
    db: Session,
    patient: "Patient",
    series_type: str,
    samples: list[dict[str, Any]],
) -> None:
    """Update patient summary with activity data.

    For steps data, we calculate active minutes using the OW repository method.
    For other activity data (distance, calories), we update directly.
    """
    from datetime import date, timedelta

    from app.models.data_point_series import DataPointSeries
    from app.repositories.data_point_series_repository import DataPointSeriesRepository
    from sense_loop.services.summary_service import SummaryService

    if not samples or not patient.ow_user_id:
        return

    service = SummaryService(db)

    # For steps, calculate active minutes
    if series_type == "steps":
        # Calculate today's active minutes from step data
        repo = DataPointSeriesRepository(DataPointSeries)
        today = date.today()
        tomorrow = today + timedelta(days=1)

        try:
            activity_data = repo.get_daily_active_minutes(
                db,
                patient.ow_user_id,
                today,
                tomorrow,
                active_threshold=30,  # 30 steps/minute = active
            )

            # activity_data is a list of ActiveMinutesResult TypedDicts
            # Find today's data in the list
            day_data = next(
                (d for d in activity_data if d["activity_date"] == today),
                None
            ) if activity_data else None

            if day_data:
                active_minutes = day_data["active_minutes"]

                # Also sum up steps from samples
                total_steps = sum(s.get("value", 0) for s in samples if s.get("value"))

                logger.info(
                    "Updating activity for patient %s: %d steps, %d active minutes",
                    patient.id,
                    total_steps,
                    active_minutes,
                )

                service.update_activity(
                    patient_id=patient.id,
                    steps=total_steps,
                    active_minutes=active_minutes,
                )
        except Exception as e:
            logger.warning("Failed to calculate active minutes: %s", str(e))

    # For exercise time, update active minutes directly
    elif series_type in ("exercise_time", "apple_exercise_time"):
        # Sum exercise minutes from samples
        total_minutes = sum(int(s.get("value", 0)) for s in samples if s.get("value"))
        if total_minutes > 0:
            service.update_activity(
                patient_id=patient.id,
                active_minutes=total_minutes,
            )

    # For distance data
    elif series_type in ("distance", "distance_walking_running"):
        # Get total distance in meters
        total_distance = sum(float(s.get("value", 0)) for s in samples if s.get("value"))
        if total_distance > 0:
            service.update_activity(
                patient_id=patient.id,
                distance_meters=total_distance,
            )

    # For active calories
    elif series_type in ("active_energy", "active_energy_burned"):
        total_calories = sum(float(s.get("value", 0)) for s in samples if s.get("value"))
        if total_calories > 0:
            service.update_activity(
                patient_id=patient.id,
                active_calories=total_calories,
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


def _trigger_task_completion(
    patient_id: UUID,
    data_type: str,
    samples: list[dict[str, Any]],
) -> None:
    """Trigger async task completion check via Celery.

    Dispatches a Celery task to check if any pending instruction tasks
    can be auto-completed by this incoming data.
    """
    if not samples:
        return

    # Get the latest sample for task completion
    latest = max(samples, key=lambda s: s.get("timestamp", ""))
    value = latest.get("value")
    timestamp = latest.get("timestamp")

    if value is None:
        return

    # For blood pressure, we need both systolic and diastolic
    # Build a dict if this is a BP reading
    if data_type in ("blood_pressure_systolic", "blood_pressure_diastolic"):
        # Store value for later pairing - for now, just pass the individual value
        data_value = {"systolic" if "systolic" in data_type else "diastolic": value}
        data_type = "blood_pressure"
    else:
        data_value = value

    try:
        from app.integrations.celery.tasks.instruction_tasks import process_data_for_tasks
        from uuid import uuid4

        # Generate a pseudo data_id for linking
        # In a real implementation, this would be the actual data record ID
        data_id = str(uuid4())

        process_data_for_tasks.delay(
            patient_id=str(patient_id),
            data_type=data_type,
            data_id=data_id,
            data_value=data_value,
            timestamp=timestamp if isinstance(timestamp, str) else timestamp.isoformat() if timestamp else datetime.utcnow().isoformat(),
        )

        logger.debug(
            "Triggered task completion check for patient %s with %s data",
            patient_id,
            data_type,
        )

    except Exception as e:
        # Don't fail the main data processing if task completion fails
        logger.warning(
            "Failed to trigger task completion check: %s", str(e)
        )
