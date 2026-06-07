"""Convenience helpers for emitting outgoing webhook events.

Call these functions after data is committed to the database.
Each schedules a Celery task and returns immediately — Svix delivery
happens in the worker process.

Events are dispatched to both:
- Svix (for developer webhooks)
- Medplum (for FHIR integration, when enabled)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from app.config import settings
from app.constants.webhooks.events import SERIES_TYPE_TO_GRANULAR_EVENT, SERIES_TYPE_TO_GROUP_EVENT
from app.schemas.webhooks.event_types import WebhookEventType

logger = logging.getLogger(__name__)

# Maximum number of samples included in a single Svix message.
# At ~200 bytes per serialised sample, 2 500 samples ≈ 500 KB — well within
# Svix's 1 MB payload limit.  Batches larger than this are split into
# consecutive chunk events, each carrying a ``chunk_index`` / ``total_chunks``
# envelope so consumers can reassemble if needed.
SVIX_MAX_SAMPLES_PER_EVENT = 2500

# Svix eventId must match [a-zA-Z0-9\-_.] — colons, plus-signs, and other
# characters in ISO 8601 timestamps are not allowed.
_SVIX_ID_SAFE = re.compile(r"[^a-zA-Z0-9\-_.]")


def _safe_key(raw: str) -> str:
    """Replace characters forbidden in a Svix eventId with underscores."""
    return _SVIX_ID_SAFE.sub("_", raw)


def _dispatch(
    event_type: str,
    payload: dict[str, Any],
    *,
    channels: list[str] | None = None,
    idempotency_key: str | None = None,
) -> None:
    """Schedule the Celery emit task.

    Import is deferred to avoid circular dependencies. Silently drops the
    event when the broker (Redis) is unreachable so that data ingestion is
    never blocked by webhook infrastructure.
    """
    try:
        from app.integrations.celery.tasks.emit_webhook_event_task import emit_webhook_event

        emit_webhook_event.delay(event_type, payload, channels=channels, idempotency_key=idempotency_key)
    except Exception:
        logger.warning("Could not enqueue webhook event %s", event_type, exc_info=True)


def _dispatch_medplum_workout(
    *,
    user_id: UUID,
    workout_data: dict[str, Any],
    medplum_patient_id: str | None = None,
) -> None:
    """Schedule Medplum workout delivery task.

    Silently skips if Medplum integration is not enabled.
    """
    if not settings.medplum_enabled:
        return

    try:
        from app.integrations.celery.tasks.medplum_tasks import send_workout_to_medplum

        send_workout_to_medplum.delay(
            user_id=str(user_id),
            workout_data=workout_data,
            medplum_patient_id=medplum_patient_id,
        )
    except Exception:
        logger.warning("Could not enqueue Medplum workout event", exc_info=True)


def _dispatch_medplum_sleep(
    *,
    user_id: UUID,
    sleep_data: dict[str, Any],
    medplum_patient_id: str | None = None,
) -> None:
    """Schedule Medplum sleep delivery task.

    Silently skips if Medplum integration is not enabled.

    DEPRECATED: Use _dispatch_medplum_sleep_batch for better efficiency during bulk syncs.
    """
    if not settings.medplum_enabled:
        return

    try:
        from app.integrations.celery.tasks.medplum_tasks import send_sleep_to_medplum

        send_sleep_to_medplum.delay(
            user_id=str(user_id),
            sleep_data=sleep_data,
            medplum_patient_id=medplum_patient_id,
        )
    except Exception:
        logger.warning("Could not enqueue Medplum sleep event", exc_info=True)


# SENSE-LOOP: Added batch dispatch function to avoid rate limiting during historical syncs
def _dispatch_medplum_sleep_batch(
    *,
    user_id: UUID,
    sleep_sessions: list[dict[str, Any]],
    medplum_patient_id: str | None = None,
) -> None:
    """Schedule Medplum sleep batch delivery task.

    Used for efficient delivery of multiple sleep sessions in a single request.
    Determines if sessions are historical based on the configured threshold.

    Silently skips if Medplum integration is not enabled or no sessions provided.
    """
    if not settings.medplum_enabled:
        return

    if not sleep_sessions:
        return

    try:
        from app.integrations.celery.tasks.medplum_tasks import send_sleep_batch_to_medplum

        # Determine if this is historical data based on the most recent session end time
        end_times = [s.get("end_datetime") for s in sleep_sessions if s.get("end_datetime")]
        is_historical = False

        if end_times:
            from datetime import datetime, timezone

            most_recent = max(end_times)
            # Parse the ISO timestamp
            if isinstance(most_recent, str):
                # Handle timezone-aware ISO strings
                if most_recent.endswith("Z"):
                    most_recent = most_recent.replace("Z", "+00:00")
                try:
                    most_recent_dt = datetime.fromisoformat(most_recent)
                    if most_recent_dt.tzinfo is None:
                        most_recent_dt = most_recent_dt.replace(tzinfo=timezone.utc)
                    now = datetime.now(timezone.utc)
                    hours_old = (now - most_recent_dt).total_seconds() / 3600
                    is_historical = hours_old > settings.medplum_historical_threshold_hours
                except (ValueError, TypeError):
                    # If we can't parse the timestamp, assume it's historical to be safe
                    is_historical = True

        # SENSE-LOOP: Use apply_async with small countdown to reduce contention with vitals
        send_sleep_batch_to_medplum.apply_async(
            kwargs={
                "user_id": str(user_id),
                "sleep_sessions": sleep_sessions,
                "medplum_patient_id": medplum_patient_id,
                "is_historical": is_historical,
            },
            countdown=1,  # Small delay to let vitals batches start first
        )
    except Exception:
        logger.warning("Could not enqueue Medplum sleep batch event", exc_info=True)


def _dispatch_medplum_hr(
    *,
    user_id: UUID,
    value: int,
    timestamp: str,
    source_provider: str,
    source_device: str | None = None,
    medplum_patient_id: str | None = None,
    is_historical: bool = False,
) -> None:
    """Schedule Medplum HR processing task.

    HR data goes through context detection and anomaly processing.
    Silently skips if Medplum integration is not enabled.

    DEPRECATED: Use _dispatch_medplum_hr_batch for better efficiency.
    """
    if not settings.medplum_enabled:
        return

    try:
        from app.integrations.celery.tasks.medplum_tasks import process_hr_for_medplum

        process_hr_for_medplum.delay(
            user_id=str(user_id),
            value=value,
            timestamp=timestamp,
            source_provider=source_provider,
            source_device=source_device,
            medplum_patient_id=medplum_patient_id,
            is_historical=is_historical,
        )
    except Exception:
        logger.warning("Could not enqueue Medplum HR event", exc_info=True)


def _dispatch_medplum_hr_batch(
    *,
    user_id: UUID,
    readings: list[dict[str, Any]],
    source_provider: str,
    source_device: str | None = None,
    medplum_patient_id: str | None = None,
) -> None:
    """Schedule Medplum HR batch processing task.

    Uses efficient batch context detection and handles historical data.
    HR data goes through context detection and anomaly processing.

    Automatically determines if data is historical based on timestamps.
    Silently skips if Medplum integration is not enabled.
    """
    if not settings.medplum_enabled:
        return

    if not readings:
        return

    try:
        from app.integrations.celery.tasks.medplum_tasks import process_hr_batch_for_medplum

        # Determine if this batch is historical based on the most recent reading
        historical_threshold = timedelta(hours=settings.medplum_historical_threshold_hours)
        now = datetime.now(timezone.utc)

        batch_timestamps = []
        for reading in readings:
            ts_str = reading.get("timestamp")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    batch_timestamps.append(ts)
                except (ValueError, TypeError):
                    pass

        is_historical = False
        if batch_timestamps:
            newest_reading = max(batch_timestamps)
            is_historical = (now - newest_reading) > historical_threshold

        # Use apply_async with small countdown to stagger with other tasks
        process_hr_batch_for_medplum.apply_async(
            kwargs={
                "user_id": str(user_id),
                "readings": readings,
                "source_provider": source_provider,
                "source_device": source_device,
                "medplum_patient_id": medplum_patient_id,
                "is_historical": is_historical,
            },
            countdown=0.5,  # Small delay
        )

        logger.debug(
            "Enqueued Medplum HR batch: user=%s, count=%d, is_historical=%s",
            user_id,
            len(readings),
            is_historical,
        )

    except Exception:
        logger.warning(
            "Could not enqueue Medplum HR batch (%d readings)",
            len(readings),
            exc_info=True,
        )


def _dispatch_medplum_vitals(
    *,
    event_type: str,
    user_id: UUID,
    timestamp: str,
    data: dict[str, Any],
    medplum_patient_id: str | None = None,
) -> None:
    """Schedule Medplum vitals delivery task.

    Used for low-frequency vitals like SpO2, weight, etc.
    Silently skips if Medplum integration is not enabled.
    """
    if not settings.medplum_enabled:
        return

    try:
        from app.integrations.celery.tasks.medplum_tasks import send_vitals_to_medplum

        send_vitals_to_medplum.delay(
            event_type=event_type,
            user_id=str(user_id),
            timestamp=timestamp,
            data=data,
            medplum_patient_id=medplum_patient_id,
        )
    except Exception:
        logger.warning("Could not enqueue Medplum vitals event for %s", event_type, exc_info=True)


def _dispatch_medplum_vitals_batch(
    *,
    event_type: str,
    user_id: UUID,
    samples: list[dict[str, Any]],
    series_type: str,
    source_provider: str,
    source_device: str | None = None,
    medplum_patient_id: str | None = None,
) -> None:
    """Schedule Medplum vitals batch delivery task.

    Sends multiple samples in a single request to avoid rate limiting.
    Automatically splits into multiple batches if samples exceed batch size.
    Flags samples older than the historical threshold to skip alert evaluation.

    Silently skips if Medplum integration is not enabled.
    """
    if not settings.medplum_enabled:
        return

    if not samples:
        return

    try:
        from app.integrations.celery.tasks.medplum_tasks import send_vitals_batch_to_medplum

        batch_size = settings.medplum_vitals_batch_size
        historical_threshold = timedelta(hours=settings.medplum_historical_threshold_hours)
        now = datetime.now(timezone.utc)

        # SENSE-LOOP: Stagger batch dispatch to avoid overwhelming Medplum
        # Each batch is delayed by batch_index * 0.5 seconds
        batch_delay_seconds = 0.5

        # Split samples into batches
        batch_index = 0
        for i in range(0, len(samples), batch_size):
            batch = samples[i : i + batch_size]

            # Determine if this batch is historical based on the most recent sample
            # If the newest sample in the batch is older than threshold, it's historical
            batch_timestamps = []
            for sample in batch:
                ts_str = sample.get("timestamp")
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        batch_timestamps.append(ts)
                    except (ValueError, TypeError):
                        pass

            is_historical = False
            if batch_timestamps:
                newest_sample = max(batch_timestamps)
                is_historical = (now - newest_sample) > historical_threshold

            # SENSE-LOOP: Use apply_async with countdown to stagger execution
            countdown = batch_index * batch_delay_seconds
            send_vitals_batch_to_medplum.apply_async(
                kwargs={
                    "event_type": event_type,
                    "user_id": str(user_id),
                    "samples": batch,
                    "series_type": series_type,
                    "source_provider": source_provider,
                    "source_device": source_device,
                    "medplum_patient_id": medplum_patient_id,
                    "is_historical": is_historical,
                },
                countdown=countdown,
            )
            batch_index += 1

            logger.debug(
                "Enqueued Medplum vitals batch: type=%s, samples=%d, is_historical=%s",
                series_type,
                len(batch),
                is_historical,
            )

    except Exception:
        logger.warning(
            "Could not enqueue Medplum vitals batch for %s (%d samples)",
            event_type,
            len(samples),
            exc_info=True,
        )


def on_workout_created(
    *,
    record_id: UUID,
    user_id: UUID,
    provider: str,
    device: str | None,
    workout_type: str | None,
    start_time: str,
    end_time: str,
    zone_offset: str | None,
    duration_seconds: float | None,
    calories_kcal: float | None = None,
    distance_meters: float | None = None,
    avg_heart_rate_bpm: int | None = None,
    max_heart_rate_bpm: int | None = None,
    elevation_gain_meters: float | None = None,
    avg_pace_sec_per_km: int | None = None,
    medplum_patient_id: str | None = None,
) -> None:
    # Dispatch to Svix (developer webhooks)
    _dispatch(
        WebhookEventType.WORKOUT_CREATED,
        {
            "type": WebhookEventType.WORKOUT_CREATED,
            "data": {
                "id": str(record_id),
                "user_id": str(user_id),
                "type": workout_type,
                "start_time": start_time,
                "end_time": end_time,
                "zone_offset": zone_offset,
                "duration_seconds": duration_seconds,
                "source": {"provider": provider, "device": device},
                "calories_kcal": calories_kcal,
                "distance_meters": distance_meters,
                "avg_heart_rate_bpm": avg_heart_rate_bpm,
                "max_heart_rate_bpm": max_heart_rate_bpm,
                "avg_pace_sec_per_km": avg_pace_sec_per_km,
                "elevation_gain_meters": elevation_gain_meters,
            },
        },
        idempotency_key=f"workout.created.{record_id}",
        channels=[f"user.{user_id}"],
    )

    # Dispatch to Medplum (FHIR integration)
    _dispatch_medplum_workout(
        user_id=user_id,
        workout_data={
            "id": str(record_id),
            "type": workout_type,
            "start_datetime": start_time,
            "end_datetime": end_time,
            "zone_offset": zone_offset,
            "duration_seconds": duration_seconds,
            "source_provider": provider,
            "source_device": device,
            "calories_kcal": calories_kcal,
            "distance_meters": distance_meters,
            "avg_heart_rate_bpm": avg_heart_rate_bpm,
            "max_heart_rate_bpm": max_heart_rate_bpm,
            "avg_pace_sec_per_km": avg_pace_sec_per_km,
            "elevation_gain_meters": elevation_gain_meters,
        },
        medplum_patient_id=medplum_patient_id,
    )


def on_sleep_created(
    *,
    record_id: UUID,
    user_id: UUID,
    provider: str,
    device: str | None,
    start_time: str,
    end_time: str,
    zone_offset: str | None,
    duration_seconds: float | None,
    efficiency_percent: float | None = None,
    stages: dict[str, int | None] | None = None,
    is_nap: bool | None = None,
    medplum_patient_id: str | None = None,
    # SENSE-LOOP: Added collector parameter for batch webhook dispatch
    medplum_sleep_collector: list[dict[str, Any]] | None = None,
) -> None:
    """Emit webhook event for a created sleep session.

    Args:
        medplum_sleep_collector: If provided, append sleep data to this list instead of
            dispatching immediately to Medplum. Use flush_medplum_sleep_batch() after
            batch processing to dispatch all collected sleep sessions at once.
    """
    # Dispatch to Svix (developer webhooks)
    _dispatch(
        WebhookEventType.SLEEP_CREATED,
        {
            "type": WebhookEventType.SLEEP_CREATED,
            "data": {
                "id": str(record_id),
                "user_id": str(user_id),
                "start_time": start_time,
                "end_time": end_time,
                "zone_offset": zone_offset,
                "duration_seconds": duration_seconds,
                "source": {"provider": provider, "device": device},
                "efficiency_percent": efficiency_percent,
                "stages": stages,
                "is_nap": is_nap,
            },
        },
        idempotency_key=f"sleep.created.{record_id}",
        channels=[f"user.{user_id}"],
    )

    # Build sleep data dict for Medplum
    sleep_data = {
        "id": str(record_id),
        "start_datetime": start_time,
        "end_datetime": end_time,
        "zone_offset": zone_offset,
        "duration_seconds": duration_seconds,
        "source_provider": provider,
        "source_device": device,
        "efficiency_percent": efficiency_percent,
        "stages": stages,
        "is_nap": is_nap,
    }

    # SENSE-LOOP: If collector provided, add to batch; otherwise dispatch immediately
    if medplum_sleep_collector is not None:
        medplum_sleep_collector.append(sleep_data)
    else:
        # Dispatch to Medplum (FHIR integration) immediately
        _dispatch_medplum_sleep(
            user_id=user_id,
            sleep_data=sleep_data,
            medplum_patient_id=medplum_patient_id,
        )


# SENSE-LOOP: Added flush function for batch webhook dispatch
def flush_medplum_sleep_batch(
    *,
    user_id: UUID,
    sleep_sessions: list[dict[str, Any]],
    medplum_patient_id: str | None = None,
) -> None:
    """Dispatch collected sleep sessions to Medplum as a batch.

    Call this after batch processing when using medplum_sleep_collector
    in on_sleep_created().
    """
    if not sleep_sessions:
        return

    _dispatch_medplum_sleep_batch(
        user_id=user_id,
        sleep_sessions=sleep_sessions,
        medplum_patient_id=medplum_patient_id,
    )


def _dispatch_sense_loop(
    *,
    user_id: UUID,
    series_type: str,
    samples: list[dict[str, Any]],
    provider: str | None = None,
) -> None:
    """Dispatch timeseries data to Sense Loop for alert evaluation.

    Silently skips if Sense Loop extension is not enabled.
    """
    if not settings.sense_loop_enabled:
        return

    if not samples:
        return

    try:
        from app.integrations.celery.tasks.sense_loop_tasks import process_vitals_for_sense_loop

        process_vitals_for_sense_loop.delay(
            user_id=str(user_id),
            series_type=series_type,
            samples=samples,
            provider=provider,
        )
    except Exception:
        logger.warning("Could not enqueue Sense Loop vitals event for %s", series_type, exc_info=True)


def on_timeseries_batch_saved(
    *,
    user_id: UUID,
    provider: str,
    series_type: str,
    sample_count: int,
    start_time: str | None = None,
    end_time: str | None = None,
    samples: list[dict[str, Any]] | None = None,
    medplum_patient_id: str | None = None,
    source_device: str | None = None,
) -> None:
    """Emit one webhook event per data-type per ingestion batch.

    Each event carries the full ``samples`` array so consumers can operate in
    a webhook-first architecture without issuing follow-up API calls.

    When ``samples`` exceeds ``SVIX_MAX_SAMPLES_PER_EVENT`` the batch is split
    into multiple consecutive chunk events.  Every chunk includes
    ``chunk_index`` (0-based) and ``total_chunks`` so consumers can detect and
    reassemble split deliveries.  Single-chunk payloads omit these fields to
    keep the common case clean.

    Two events are emitted per batch:
    - a *group* event (e.g. ``heart_rate.created``) for broad subscriptions
    - a *granular* event (e.g. ``series.resting_heart_rate.created``) for
      narrow subscriptions to a specific metric
    """
    group_event = SERIES_TYPE_TO_GROUP_EVENT.get(series_type)
    if group_event is None:
        return
    granular_event = SERIES_TYPE_TO_GRANULAR_EVENT.get(series_type)
    if granular_event and granular_event != group_event:
        event_types_to_emit = [group_event, granular_event]
    else:
        event_types_to_emit = [group_event]
    samples = samples or []

    def _emit(event_type: str, payload_data: dict[str, Any], ikey: str) -> None:
        _dispatch(
            event_type,
            {"type": event_type, "data": payload_data},
            idempotency_key=_safe_key(f"{ikey}.{event_type}"),
            channels=[f"user.{user_id}"],
        )

    if len(samples) <= SVIX_MAX_SAMPLES_PER_EVENT:
        base_key = f"timeseries.{user_id}.{provider}.{series_type}.{start_time or ''}.{end_time or ''}"
        data: dict[str, Any] = {
            "user_id": str(user_id),
            "provider": provider,
            "series_type": series_type,
            "sample_count": sample_count,
            "start_time": start_time,
            "end_time": end_time,
            "samples": samples,
        }
        for event_type in event_types_to_emit:
            _emit(event_type, data, base_key)
    else:
        chunks = [
            samples[i : i + SVIX_MAX_SAMPLES_PER_EVENT] for i in range(0, len(samples), SVIX_MAX_SAMPLES_PER_EVENT)
        ]
        total_chunks = len(chunks)
        for chunk_index, chunk in enumerate(chunks):
            chunk_start = chunk[0]["timestamp"] if chunk else start_time
            chunk_end = chunk[-1]["timestamp"] if chunk else end_time
            base_key = (
                f"timeseries.{user_id}.{provider}.{series_type}.{start_time or ''}.{end_time or ''}.chunk{chunk_index}"
            )
            data = {
                "user_id": str(user_id),
                "provider": provider,
                "series_type": series_type,
                "sample_count": sample_count,
                "start_time": chunk_start,
                "end_time": chunk_end,
                "samples": chunk,
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
            }
            for event_type in event_types_to_emit:
                _emit(event_type, data, base_key)

    # Dispatch vitals to Medplum using batched delivery to avoid rate limiting
    # HR uses specialized processing with context detection and anomaly alerts
    # Other vitals are batched for efficient delivery

    if series_type == "heart_rate" and samples:
        # HR needs special processing with context detection and anomaly detection
        valid_readings = [
            {"value": s.get("value"), "timestamp": s.get("timestamp")}
            for s in samples
            if s.get("value") is not None and s.get("timestamp") is not None
        ]

        if valid_readings:
            _dispatch_medplum_hr_batch(
                user_id=user_id,
                readings=valid_readings,
                source_provider=provider,
                source_device=source_device,
                medplum_patient_id=medplum_patient_id,
            )
    else:
        # Other vitals use the generic batch path (no anomaly detection)
        medplum_vitals_types = (
            "spo2",
            "blood_oxygen",
            "oxygen_saturation",
            "weight",
            "body_temperature",
            "respiratory_rate",
            "blood_pressure_systolic",
            "blood_pressure_diastolic",
            "heart_rate_variability_sdnn",
            "heart_rate_variability_rmssd",
        )

        if series_type in medplum_vitals_types and samples:
            # Filter to valid samples only
            valid_samples = [
                {"value": s.get("value"), "timestamp": s.get("timestamp")}
                for s in samples
                if s.get("value") is not None and s.get("timestamp") is not None
            ]

            if valid_samples:
                _dispatch_medplum_vitals_batch(
                    event_type=f"series.{series_type}.created",
                    user_id=user_id,
                    samples=valid_samples,
                    series_type=series_type,
                    source_provider=provider,
                    source_device=source_device,
                    medplum_patient_id=medplum_patient_id,
                )

    # Dispatch to Sense Loop for alert evaluation
    # SL handles its own vital type mapping and patient lookup
    _dispatch_sense_loop(
        user_id=user_id,
        series_type=series_type,
        samples=samples or [],
        provider=provider,
    )


def on_connection_created(
    *,
    user_id: UUID,
    provider: str,
    connection_id: UUID,
    connected_at: str,
) -> None:
    _dispatch(
        WebhookEventType.CONNECTION_CREATED,
        {
            "type": WebhookEventType.CONNECTION_CREATED,
            "data": {
                "user_id": str(user_id),
                "provider": provider,
                "connection_id": str(connection_id),
                "connected_at": connected_at,
            },
        },
        idempotency_key=f"connection.created.{user_id}.{provider}",
        channels=[f"user.{user_id}"],
    )
