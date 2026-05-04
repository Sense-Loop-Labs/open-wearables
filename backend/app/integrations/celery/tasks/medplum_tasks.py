"""Celery tasks for Medplum FHIR integration.

SENSE-LOOP ADDITION: This entire module is a Sense Loop addition for clinical data sync.

Handles:
- Processing HR readings with context-aware anomaly detection
- Sustained anomaly detection (5-minute window)
- Hourly HR aggregation and delivery
- HR baseline calculation
- Direct vitals delivery to Medplum
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from celery import shared_task
from sqlalchemy import func, select

from app.config import settings
from app.database import SessionLocal
from app.integrations.redis_client import get_redis_client
from app.models import DataPointSeries, DataSource, User
from app.models.hr_analysis import HRBaseline
from app.services.medplum.context_detector import ContextDetector
from app.services.medplum.hr_anomaly_service import HRAnomalyService
from app.services.medplum.hr_processor import HRContext, HRProcessor, HRReading, HRThresholds
from app.services.medplum.webhook import medplum_webhook

logger = logging.getLogger(__name__)


def _get_medplum_patient_id(user_id: str | UUID, provided_id: str | None = None) -> str | None:
    """Get Medplum Patient ID from user's external_user_id if not provided.

    The external_user_id field on User is used to store the linked Medplum Patient ID.
    """
    if provided_id:
        return provided_id

    try:
        user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
        with SessionLocal() as db:
            user = db.execute(select(User).where(User.id == user_uuid)).scalar_one_or_none()
            if user and user.external_user_id:
                return user.external_user_id
    except Exception:
        logger.debug("Could not look up external_user_id for user %s", user_id)

    return None


@shared_task(
    name="app.integrations.celery.tasks.medplum_tasks.process_hr_for_medplum",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
    acks_late=True,
)
def process_hr_for_medplum(
    self: Any,
    user_id: str,
    value: int,
    timestamp: str,
    source_provider: str,
    source_device: str | None = None,
    medplum_patient_id: str | None = None,
    is_historical: bool = False,
) -> dict[str, Any]:
    """Process a single heart rate reading for Medplum integration.

    Enhanced with:
    - Active energy detection (catches stationary exercise)
    - Post-workout recovery period detection
    - Sustained anomaly buffer (5-minute window)
    - Context data capture for anomaly records
    - Historical data optimization (skip anomaly detection)

    Called when heart_rate events are received. Detects context,
    checks for anomalies, and buffers for aggregation.

    Args:
        is_historical: If True, skip anomaly detection (for bulk syncs).
                      Historical data is still buffered for aggregation.
    """
    if not medplum_webhook.is_enabled():
        logger.debug("Medplum integration not enabled, skipping HR processing")
        return {"processed": False, "reason": "medplum_disabled"}

    try:
        redis_client = get_redis_client()
        processor = HRProcessor(redis_client)

        # Parse timestamp
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        user_uuid = UUID(user_id)

        # Look up Medplum Patient ID if not provided
        patient_id = _get_medplum_patient_id(user_uuid, medplum_patient_id)

        # For historical data, use simplified processing (no anomaly detection)
        if is_historical:
            # Use UNKNOWN context for historical data to avoid DB queries
            reading = HRReading(
                value=value,
                timestamp=ts,
                context=HRContext.UNKNOWN,
                user_id=user_uuid,
                medplum_patient_id=patient_id,
                source_provider=source_provider,
                source_device=source_device,
            )
            # Buffer for aggregation only
            processor._buffer_reading(reading)
            return {
                "processed": True,
                "anomaly_detected": False,
                "context": HRContext.UNKNOWN.value,
                "is_historical": True,
            }

        # Real-time processing with full context detection
        with SessionLocal() as db:
            detector = ContextDetector(db)
            context = detector.detect_context(user_uuid, ts)

            # Gather additional context data for anomaly records
            context_data = {
                "minutes_since_workout": detector.get_minutes_since_workout(user_uuid, ts),
                "recent_steps": detector.get_recent_steps(user_uuid, ts),
                "recent_energy": float(detector.get_recent_energy(user_uuid, ts)),
            }

        # Get thresholds (could be patient-specific in the future)
        thresholds = HRThresholds.from_settings()

        # Process the reading
        reading = HRReading(
            value=value,
            timestamp=ts,
            context=context,
            user_id=user_uuid,
            medplum_patient_id=patient_id,
            source_provider=source_provider,
            source_device=source_device,
        )

        # Always buffer the reading for hourly aggregation
        processor._buffer_reading(reading)

        # Check for potential anomaly
        if processor.is_potential_anomaly(reading, thresholds):
            # Buffer in the anomaly buffer for sustained detection
            processor.buffer_potential_anomaly(reading)

            # Check if we have sustained elevation
            sustained = processor.check_sustained_anomaly(user_uuid, ts)
            if sustained:
                # Record and dispatch the anomaly
                with SessionLocal() as db:
                    anomaly_service = HRAnomalyService(db)
                    anomaly_record = anomaly_service.record_anomaly(
                        user_id=user_uuid,
                        anomaly=sustained,
                        context_data=context_data,
                        medplum_patient_id=patient_id,
                    )

                # Clear the anomaly buffer after alerting
                processor.clear_anomaly_buffer(user_uuid)

                return {
                    "processed": True,
                    "anomaly_detected": True,
                    "anomaly_sent": anomaly_record.sent_to_medplum_at is not None,
                    "anomaly_id": str(anomaly_record.id),
                    "context": context.value,
                    "reason": sustained.reason,
                }

        return {
            "processed": True,
            "anomaly_detected": False,
            "context": context.value,
        }

    except Exception as exc:
        logger.error("Error processing HR for Medplum: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


@shared_task(
    name="app.integrations.celery.tasks.medplum_tasks.aggregate_hr_hourly",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def aggregate_hr_hourly(self: Any) -> dict[str, Any]:
    """Periodic task to compute and send hourly HR aggregations.

    Runs every hour via Celery Beat. Processes the previous hour's
    data for all users with buffered readings.
    """
    if not medplum_webhook.is_enabled():
        logger.debug("Medplum integration not enabled, skipping HR aggregation")
        return {"processed": False, "reason": "medplum_disabled"}

    try:
        redis_client = get_redis_client()
        processor = HRProcessor(redis_client)

        # Process previous hour
        now = datetime.utcnow()
        hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)

        # Get all users with HR data
        user_ids = processor.get_users_with_buffered_data()

        sent_count = 0
        error_count = 0

        for user_id in user_ids:
            try:
                # Compute aggregations
                aggregations = processor.compute_hourly_aggregation(user_id, hour_start)

                # Send each aggregation to Medplum
                for agg in aggregations:
                    payload = processor.create_aggregation_payload(agg)
                    success = medplum_webhook.send_sync(payload)
                    if success:
                        sent_count += 1
                    else:
                        error_count += 1

                # Cleanup old data
                processor.cleanup_old_data(
                    user_id,
                    before=now - timedelta(hours=processor.buffer_ttl_hours),
                )

            except Exception as e:
                logger.error("Error aggregating HR for user %s: %s", user_id, e)
                error_count += 1

        logger.info(
            "HR hourly aggregation complete: %d sent, %d errors, %d users",
            sent_count,
            error_count,
            len(user_ids),
        )

        return {
            "processed": True,
            "users_processed": len(user_ids),
            "aggregations_sent": sent_count,
            "errors": error_count,
            "hour_start": hour_start.isoformat(),
        }

    except Exception as exc:
        logger.error("Error in HR hourly aggregation: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


@shared_task(
    name="app.integrations.celery.tasks.medplum_tasks.process_hr_batch_for_medplum",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    acks_late=True,
)
def process_hr_batch_for_medplum(
    self: Any,
    user_id: str,
    readings: list[dict[str, Any]],
    source_provider: str,
    source_device: str | None = None,
    medplum_patient_id: str | None = None,
    is_historical: bool = False,
) -> dict[str, Any]:
    """Process a batch of HR readings efficiently.

    Uses batch context detection to minimize database queries.
    For historical data, skips anomaly detection entirely.

    Args:
        user_id: Open Wearables user ID
        readings: List of dicts with 'value' and 'timestamp' keys
        source_provider: Data source provider
        source_device: Device model (optional)
        medplum_patient_id: Medplum Patient ID (optional)
        is_historical: If True, skip anomaly detection

    This is much more efficient than calling process_hr_for_medplum
    individually for each reading during bulk syncs.
    """
    if not medplum_webhook.is_enabled():
        logger.debug("Medplum integration not enabled, skipping HR batch processing")
        return {"processed": False, "reason": "medplum_disabled", "count": len(readings)}

    if not readings:
        return {"processed": True, "count": 0}

    try:
        redis_client = get_redis_client()
        processor = HRProcessor(redis_client)
        user_uuid = UUID(user_id)

        # Look up Medplum Patient ID if not provided
        patient_id = _get_medplum_patient_id(user_uuid, medplum_patient_id)

        # Parse all timestamps
        parsed_readings = []
        for r in readings:
            try:
                ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
                parsed_readings.append({"value": int(r["value"]), "timestamp": ts})
            except (KeyError, ValueError) as e:
                logger.debug("Skipping invalid HR reading: %s", e)
                continue

        if not parsed_readings:
            return {"processed": True, "count": 0, "error": "no valid readings"}

        # For historical data, skip context detection and anomaly checking
        if is_historical:
            for r in parsed_readings:
                reading = HRReading(
                    value=r["value"],
                    timestamp=r["timestamp"],
                    context=HRContext.UNKNOWN,
                    user_id=user_uuid,
                    medplum_patient_id=patient_id,
                    source_provider=source_provider,
                    source_device=source_device,
                )
                processor._buffer_reading(reading)

            logger.info(
                "Processed %d historical HR readings for user %s",
                len(parsed_readings),
                user_id,
            )
            return {
                "processed": True,
                "count": len(parsed_readings),
                "is_historical": True,
                "anomalies_detected": 0,
            }

        # Real-time processing with batch context detection
        timestamps = [r["timestamp"] for r in parsed_readings]

        with SessionLocal() as db:
            detector = ContextDetector(db)
            # Use efficient batch detection
            contexts = detector.detect_context_batch(user_uuid, timestamps)

        thresholds = HRThresholds.from_settings()
        anomalies_detected = 0

        for r in parsed_readings:
            ts = r["timestamp"]
            context = contexts.get(ts, HRContext.UNKNOWN)

            reading = HRReading(
                value=r["value"],
                timestamp=ts,
                context=context,
                user_id=user_uuid,
                medplum_patient_id=patient_id,
                source_provider=source_provider,
                source_device=source_device,
            )

            # Buffer for aggregation
            processor._buffer_reading(reading)

            # Check for anomalies (only for non-historical real-time data)
            if processor.is_potential_anomaly(reading, thresholds):
                processor.buffer_potential_anomaly(reading)
                anomalies_detected += 1

        # After processing all readings, check for sustained anomalies
        # Use the latest timestamp for the check
        latest_ts = max(timestamps)
        sustained = processor.check_sustained_anomaly(user_uuid, latest_ts)

        anomaly_sent = False
        if sustained:
            with SessionLocal() as db:
                detector = ContextDetector(db)
                context_data = {
                    "minutes_since_workout": detector.get_minutes_since_workout(user_uuid, latest_ts),
                    "recent_steps": detector.get_recent_steps(user_uuid, latest_ts),
                    "recent_energy": float(detector.get_recent_energy(user_uuid, latest_ts)),
                }

                anomaly_service = HRAnomalyService(db)
                anomaly_record = anomaly_service.record_anomaly(
                    user_id=user_uuid,
                    anomaly=sustained,
                    context_data=context_data,
                    medplum_patient_id=patient_id,
                )
                anomaly_sent = anomaly_record.sent_to_medplum_at is not None

            processor.clear_anomaly_buffer(user_uuid)

        logger.info(
            "Processed %d HR readings for user %s, %d potential anomalies, sustained=%s",
            len(parsed_readings),
            user_id,
            anomalies_detected,
            sustained is not None,
        )

        return {
            "processed": True,
            "count": len(parsed_readings),
            "anomalies_detected": anomalies_detected,
            "sustained_anomaly": sustained is not None,
            "anomaly_sent": anomaly_sent,
        }

    except Exception as exc:
        logger.error("Error processing HR batch for Medplum: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


# SENSE-LOOP: Added rate_limit to prevent overwhelming Medplum
@shared_task(
    name="app.integrations.celery.tasks.medplum_tasks.send_vitals_to_medplum",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
    rate_limit="2/s",  # Limit to 2 requests per second to avoid 429s
)
def send_vitals_to_medplum(
    self: Any,
    event_type: str,
    user_id: str,
    timestamp: str,
    data: dict[str, Any],
    medplum_patient_id: str | None = None,
) -> dict[str, Any]:
    """Send direct vitals data to Medplum FHIR Conversion Bot.

    Used for low-frequency data like SpO2, BP, weight, etc.
    that don't need aggregation.

    DEPRECATED: Use send_vitals_batch_to_medplum for better efficiency.
    """
    if not medplum_webhook.is_enabled():
        logger.debug("Medplum integration not enabled, skipping vitals send")
        return {"sent": False, "reason": "medplum_disabled"}

    # Look up Medplum Patient ID if not provided
    patient_id = _get_medplum_patient_id(user_id, medplum_patient_id)

    payload = {
        "event_type": event_type,
        "user_id": user_id,
        "medplum_patient_id": patient_id,
        "timestamp": timestamp,
        "data": data,
    }

    try:
        success = medplum_webhook.send_sync(payload)
        return {"sent": success, "event_type": event_type}
    except Exception as exc:
        logger.error("Error sending vitals to Medplum: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


# SENSE-LOOP: Added rate_limit to prevent overwhelming Medplum with concurrent requests
@shared_task(
    name="app.integrations.celery.tasks.medplum_tasks.send_vitals_batch_to_medplum",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
    rate_limit="2/s",  # Limit to 2 batch requests per second to avoid 429s
)
def send_vitals_batch_to_medplum(
    self: Any,
    event_type: str,
    user_id: str,
    samples: list[dict[str, Any]],
    series_type: str,
    source_provider: str,
    source_device: str | None = None,
    medplum_patient_id: str | None = None,
    is_historical: bool = False,
) -> dict[str, Any]:
    """Send a batch of vitals data to Medplum FHIR Conversion Bot.

    Used for efficient delivery of multiple samples (HR, SpO2, respiratory rate, etc.)
    in a single HTTP request to avoid rate limiting.

    Args:
        event_type: The event type (e.g., "series.heart_rate.created")
        user_id: Open Wearables user ID
        samples: List of sample dicts with "value" and "timestamp" keys
        series_type: The vital type (e.g., "heart_rate", "spo2")
        source_provider: Data source provider (e.g., "apple")
        source_device: Device model (optional)
        medplum_patient_id: Medplum Patient ID (optional, will be looked up if not provided)
        is_historical: If True, the FHIR bot will store data but skip alert evaluation
    """
    if not medplum_webhook.is_enabled():
        logger.debug("Medplum integration not enabled, skipping vitals batch send")
        return {"sent": False, "reason": "medplum_disabled", "sample_count": len(samples)}

    if not samples:
        return {"sent": False, "reason": "no_samples", "sample_count": 0}

    # Look up Medplum Patient ID if not provided
    patient_id = _get_medplum_patient_id(user_id, medplum_patient_id)

    # Get time range for logging
    timestamps = [s.get("timestamp") for s in samples if s.get("timestamp")]
    time_range_start = min(timestamps) if timestamps else None
    time_range_end = max(timestamps) if timestamps else None

    payload = {
        "event_type": event_type,
        "user_id": user_id,
        "medplum_patient_id": patient_id,
        "series_type": series_type,
        "source_provider": source_provider,
        "source_device": source_device,
        "is_historical": is_historical,
        "is_batch": True,
        "sample_count": len(samples),
        "samples": samples,
    }

    try:
        success = medplum_webhook.send_sync(
            payload,
            timeout=60.0,  # Longer timeout for batch requests
        )

        if success:
            logger.info(
                "Sent vitals batch to Medplum: event_type=%s, user_id=%s, sample_count=%d, "
                "is_historical=%s, time_range=%s to %s",
                event_type,
                user_id,
                len(samples),
                is_historical,
                time_range_start,
                time_range_end,
            )
        else:
            # Enhanced logging for failed batches
            logger.error(
                "Failed to send vitals batch to Medplum after retries. "
                "event_type=%s, user_id=%s, sample_count=%d, series_type=%s, "
                "is_historical=%s, time_range=%s to %s. "
                "Data is preserved in Open Wearables database.",
                event_type,
                user_id,
                len(samples),
                series_type,
                is_historical,
                time_range_start,
                time_range_end,
            )

        return {
            "sent": success,
            "event_type": event_type,
            "sample_count": len(samples),
            "is_historical": is_historical,
        }

    except Exception as exc:
        logger.error(
            "Error sending vitals batch to Medplum: event_type=%s, user_id=%s, "
            "sample_count=%d, series_type=%s, time_range=%s to %s. Error: %s",
            event_type,
            user_id,
            len(samples),
            series_type,
            time_range_start,
            time_range_end,
            exc,
            exc_info=True,
        )
        raise self.retry(exc=exc)


# SENSE-LOOP: Added rate_limit to prevent overwhelming Medplum
@shared_task(
    name="app.integrations.celery.tasks.medplum_tasks.send_workout_to_medplum",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
    rate_limit="2/s",  # Limit to 2 requests per second to avoid 429s
)
def send_workout_to_medplum(
    self: Any,
    user_id: str,
    workout_data: dict[str, Any],
    medplum_patient_id: str | None = None,
) -> dict[str, Any]:
    """Send workout event to Medplum FHIR Conversion Bot."""
    if not medplum_webhook.is_enabled():
        logger.debug("Medplum integration not enabled, skipping workout send")
        return {"sent": False, "reason": "medplum_disabled"}

    # Look up Medplum Patient ID if not provided
    patient_id = _get_medplum_patient_id(user_id, medplum_patient_id)

    payload = {
        "event_type": "workout.created",
        "user_id": user_id,
        "medplum_patient_id": patient_id,
        "timestamp": workout_data.get("end_datetime") or workout_data.get("start_datetime"),
        "data": workout_data,
    }

    # Debug: log the payload being sent
    logger.info("Sending workout payload to Medplum: %s", payload)

    try:
        success = medplum_webhook.send_sync(payload)
        return {"sent": success, "event_type": "workout.created"}
    except Exception as exc:
        logger.error("Error sending workout to Medplum: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


# SENSE-LOOP: Added rate_limit to prevent overwhelming Medplum
@shared_task(
    name="app.integrations.celery.tasks.medplum_tasks.send_sleep_to_medplum",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
    rate_limit="2/s",  # Limit to 2 requests per second to avoid 429s
)
def send_sleep_to_medplum(
    self: Any,
    user_id: str,
    sleep_data: dict[str, Any],
    medplum_patient_id: str | None = None,
) -> dict[str, Any]:
    """Send sleep event to Medplum FHIR Conversion Bot.

    DEPRECATED: Use send_sleep_batch_to_medplum for better efficiency during bulk syncs.
    """
    if not medplum_webhook.is_enabled():
        logger.debug("Medplum integration not enabled, skipping sleep send")
        return {"sent": False, "reason": "medplum_disabled"}

    # Look up Medplum Patient ID if not provided
    patient_id = _get_medplum_patient_id(user_id, medplum_patient_id)

    payload = {
        "event_type": "sleep.created",
        "user_id": user_id,
        "medplum_patient_id": patient_id,
        "timestamp": sleep_data.get("end_datetime") or sleep_data.get("start_datetime"),
        "data": sleep_data,
    }

    try:
        success = medplum_webhook.send_sync(payload)
        return {"sent": success, "event_type": "sleep.created"}
    except Exception as exc:
        logger.error("Error sending sleep to Medplum: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


# SENSE-LOOP: Added batch task to avoid rate limiting during historical syncs
@shared_task(
    name="app.integrations.celery.tasks.medplum_tasks.send_sleep_batch_to_medplum",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
    rate_limit="2/s",  # SENSE-LOOP: Limit to 2 batch requests per second to avoid 429s
)
def send_sleep_batch_to_medplum(
    self: Any,
    user_id: str,
    sleep_sessions: list[dict[str, Any]],
    medplum_patient_id: str | None = None,
    is_historical: bool = False,
) -> dict[str, Any]:
    """Send a batch of sleep sessions to Medplum FHIR Conversion Bot.

    Used for efficient delivery of multiple sleep sessions in a single HTTP request
    to avoid rate limiting during historical syncs.

    Args:
        user_id: Open Wearables user ID
        sleep_sessions: List of sleep session dicts (each with start/end times, stages, etc.)
        medplum_patient_id: Medplum Patient ID (optional, will be looked up if not provided)
        is_historical: If True, the FHIR bot will store data but skip alert evaluation
    """
    if not medplum_webhook.is_enabled():
        logger.debug("Medplum integration not enabled, skipping sleep batch send")
        return {"sent": False, "reason": "medplum_disabled", "session_count": len(sleep_sessions)}

    if not sleep_sessions:
        return {"sent": False, "reason": "no_sessions", "session_count": 0}

    # Look up Medplum Patient ID if not provided
    patient_id = _get_medplum_patient_id(user_id, medplum_patient_id)

    # Get time range for logging
    start_times = [s.get("start_datetime") for s in sleep_sessions if s.get("start_datetime")]
    end_times = [s.get("end_datetime") for s in sleep_sessions if s.get("end_datetime")]
    time_range_start = min(start_times) if start_times else None
    time_range_end = max(end_times) if end_times else None

    payload = {
        "event_type": "sleep.batch.created",
        "user_id": user_id,
        "medplum_patient_id": patient_id,
        "is_batch": True,
        "is_historical": is_historical,
        "session_count": len(sleep_sessions),
        "sessions": sleep_sessions,
    }

    try:
        success = medplum_webhook.send_sync(
            payload,
            timeout=60.0,  # Longer timeout for batch requests
        )

        if success:
            logger.info(
                "Sent sleep batch to Medplum: user_id=%s, session_count=%d, is_historical=%s, "
                "time_range=%s to %s",
                user_id,
                len(sleep_sessions),
                is_historical,
                time_range_start,
                time_range_end,
            )
        else:
            logger.error(
                "Failed to send sleep batch to Medplum after retries. "
                "user_id=%s, session_count=%d, is_historical=%s, "
                "time_range=%s to %s. Data is preserved in Open Wearables database.",
                user_id,
                len(sleep_sessions),
                is_historical,
                time_range_start,
                time_range_end,
            )

        return {
            "sent": success,
            "event_type": "sleep.batch.created",
            "session_count": len(sleep_sessions),
            "is_historical": is_historical,
        }
    except Exception as exc:
        logger.error("Error sending sleep batch to Medplum: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


# ============ HR Baseline Calculation ============


@shared_task(
    name="app.integrations.celery.tasks.medplum_tasks.calculate_hr_baselines",
    bind=True,
    max_retries=1,
    acks_late=True,
)
def calculate_hr_baselines(self: Any) -> dict[str, Any]:
    """Nightly task to recalculate HR baselines from sleep/sedentary data.

    Calculates personalized resting HR baselines for each user based on
    HR readings during sleep sessions and sedentary periods from the
    past 14 days.

    This enables personalized alert thresholds instead of using
    fixed values for all users.

    Should be scheduled to run nightly via Celery Beat.
    """
    try:
        with SessionLocal() as db:
            # Get all users with HR data
            users = db.execute(select(User)).scalars().all()

            updated_count = 0
            error_count = 0

            for user in users:
                try:
                    _calculate_baseline_for_user(db, user.id)
                    updated_count += 1
                except Exception as e:
                    logger.error("Error calculating baseline for user %s: %s", user.id, e)
                    error_count += 1

            logger.info(
                "HR baseline calculation complete: %d updated, %d errors",
                updated_count,
                error_count,
            )

            return {
                "processed": True,
                "users_updated": updated_count,
                "errors": error_count,
            }

    except Exception as exc:
        logger.error("Error in HR baseline calculation: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


def _calculate_baseline_for_user(db: Any, user_id: UUID) -> None:
    """Calculate HR baseline for a single user.

    Uses HR readings from:
    - Sleep sessions (last 14 days)
    - Sedentary periods with low steps (last 14 days)

    Updates or creates the HRBaseline record.
    """
    from app.models import SeriesTypeDefinition

    lookback_days = 14
    start_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    # Get heart_rate series type
    hr_type = db.execute(
        select(SeriesTypeDefinition).where(
            SeriesTypeDefinition.code == "heart_rate"
        )
    ).scalar_one_or_none()

    if not hr_type:
        return

    # Get all HR readings for this user in the lookback period
    # during sleep or low-activity periods
    # For simplicity, we'll use all HR readings and filter by reasonable resting range
    hr_readings = db.execute(
        select(DataPointSeries.value)
        .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
        .where(
            DataSource.user_id == user_id,
            DataPointSeries.series_type_definition_id == hr_type.id,
            DataPointSeries.recorded_at >= start_date,
            # Filter to likely resting values (40-100 bpm)
            DataPointSeries.value >= 40,
            DataPointSeries.value <= 100,
        )
    ).scalars().all()

    if len(hr_readings) < 10:
        # Not enough data for reliable baseline
        return

    # Calculate statistics
    values = [float(v) for v in hr_readings]
    avg_hr = sum(values) / len(values)

    # Calculate standard deviation
    variance = sum((v - avg_hr) ** 2 for v in values) / len(values)
    std_hr = variance ** 0.5

    min_hr = min(values)
    max_hr = max(values)

    # Calculate elevated threshold: avg + 2*std, minimum 100
    elevated_threshold = max(int(avg_hr + 2 * std_hr), 100)

    # Update or create baseline
    baseline = db.query(HRBaseline).filter(HRBaseline.user_id == user_id).first()

    if baseline:
        baseline.resting_hr_avg = Decimal(str(round(avg_hr, 2)))
        baseline.resting_hr_std = Decimal(str(round(std_hr, 2)))
        baseline.resting_hr_min = int(min_hr)
        baseline.resting_hr_max = int(max_hr)
        baseline.sample_count = len(hr_readings)
        baseline.elevated_threshold = elevated_threshold
        baseline.last_calculated_at = datetime.now(timezone.utc)
        baseline.updated_at = datetime.now(timezone.utc)
    else:
        baseline = HRBaseline(
            user_id=user_id,
            resting_hr_avg=Decimal(str(round(avg_hr, 2))),
            resting_hr_std=Decimal(str(round(std_hr, 2))),
            resting_hr_min=int(min_hr),
            resting_hr_max=int(max_hr),
            sample_count=len(hr_readings),
            elevated_threshold=elevated_threshold,
            last_calculated_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(baseline)

    db.commit()

    logger.debug(
        "Updated HR baseline for user %s: avg=%.1f, std=%.1f, threshold=%d",
        user_id,
        avg_hr,
        std_hr,
        elevated_threshold,
    )
