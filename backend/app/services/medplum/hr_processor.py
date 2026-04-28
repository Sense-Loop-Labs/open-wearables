"""Heart Rate Processing Service for Medplum Integration.

Handles:
- Real-time anomaly detection with context-aware thresholds
- Redis buffering for aggregation
- Hourly aggregation with min/max/avg statistics
- FHIR-ready payload generation
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

import redis

from app.config import settings

logger = logging.getLogger(__name__)


class HRContext(str, Enum):
    """Activity context for heart rate readings."""

    RESTING = "resting"
    ACTIVE = "active"
    SLEEPING = "sleeping"
    EXERCISING = "exercising"
    UNKNOWN = "unknown"


@dataclass
class HRThresholds:
    """Patient-specific HR thresholds.

    Can be customized per patient via Medplum Patient extensions.
    """

    high_resting: int = 100  # Tachycardia at rest
    high_active: int = 150  # High during activity
    high_exercise: int = 180  # High during exercise
    low_resting: int = 50  # Bradycardia at rest
    low_sleeping: int = 40  # Low during sleep (more permissive)
    sustained_duration_seconds: int = 300  # 5 minutes for sustained anomaly

    @classmethod
    def from_settings(cls) -> "HRThresholds":
        """Create thresholds from application settings."""
        return cls(
            high_resting=settings.medplum_hr_high_resting,
            high_active=settings.medplum_hr_high_active,
            high_exercise=settings.medplum_hr_high_exercise,
            low_resting=settings.medplum_hr_low_resting,
            low_sleeping=settings.medplum_hr_low_sleeping,
            sustained_duration_seconds=settings.medplum_hr_anomaly_sustained_seconds,
        )


@dataclass
class HRReading:
    """Single heart rate reading with metadata."""

    value: int
    timestamp: datetime
    context: HRContext
    user_id: UUID
    medplum_patient_id: str | None
    source_provider: str
    source_device: str | None = None


@dataclass
class HRAggregation:
    """Hourly heart rate aggregation statistics."""

    period_start: datetime
    period_end: datetime
    context: HRContext
    min_hr: int
    max_hr: int
    avg_hr: float
    reading_count: int
    user_id: UUID
    medplum_patient_id: str | None


class HRProcessor:
    """Processes heart rate data for Medplum integration.

    - Buffers readings in Redis sorted sets (by timestamp)
    - Detects anomalies in real-time with context awareness
    - Computes hourly aggregations grouped by context
    - Emits FHIR-ready payloads
    """

    REDIS_KEY_PREFIX = "medplum:hr"

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.buffer_ttl_hours = settings.medplum_hr_buffer_ttl_hours

    def process_reading(
        self,
        reading: HRReading,
        thresholds: HRThresholds | None = None,
    ) -> dict[str, Any] | None:
        """Process a single HR reading.

        Returns anomaly payload if threshold breached and sustained, None otherwise.
        The reading is always buffered for later aggregation.
        """
        thresholds = thresholds or HRThresholds.from_settings()

        # 1. Check for anomaly
        anomaly_type = self._check_anomaly(reading, thresholds)
        anomaly_payload = None

        if anomaly_type:
            # Check if sustained (not a one-off spike)
            is_sustained = self._check_sustained(
                reading, thresholds.sustained_duration_seconds
            )
            if is_sustained:
                anomaly_payload = self._create_anomaly_payload(reading, anomaly_type)
                logger.info(
                    "HR anomaly detected for user %s: %s bpm (%s)",
                    reading.user_id,
                    reading.value,
                    anomaly_type,
                )

        # 2. Buffer the reading for aggregation
        self._buffer_reading(reading)

        return anomaly_payload

    def _check_anomaly(
        self,
        reading: HRReading,
        thresholds: HRThresholds,
    ) -> str | None:
        """Check if reading breaches thresholds based on context."""
        value = reading.value
        context = reading.context

        if context == HRContext.RESTING:
            if value > thresholds.high_resting:
                return "high_resting"
            if value < thresholds.low_resting:
                return "low_resting"

        elif context == HRContext.SLEEPING:
            # Still alert for high HR during sleep
            if value > thresholds.high_resting:
                return "high_sleeping"
            if value < thresholds.low_sleeping:
                return "low_sleeping"

        elif context == HRContext.ACTIVE:
            if value > thresholds.high_active:
                return "high_active"

        elif context == HRContext.EXERCISING:
            if value > thresholds.high_exercise:
                return "high_exercise"

        else:  # UNKNOWN - use conservative resting thresholds
            if value > thresholds.high_resting:
                return "high_unknown"
            if value < thresholds.low_resting:
                return "low_unknown"

        return None

    def _check_sustained(
        self,
        reading: HRReading,
        duration_seconds: int,
    ) -> bool:
        """Check if anomaly is sustained over the specified duration.

        Prevents alerting on momentary spikes by checking if the majority
        of recent readings are also anomalous.
        """
        key = f"{self.REDIS_KEY_PREFIX}:buffer:{reading.user_id}"
        cutoff = reading.timestamp - timedelta(seconds=duration_seconds)

        # Get recent readings from Redis
        try:
            recent = self.redis.zrangebyscore(
                key,
                min=cutoff.timestamp(),
                max=reading.timestamp.timestamp(),
            )
        except redis.RedisError:
            logger.warning("Redis error checking sustained anomaly", exc_info=True)
            return False

        if len(recent) < 3:  # Need at least 3 readings to confirm
            return False

        # Check if majority of recent readings are also anomalous
        anomalous_count = 0
        threshold = 100 if reading.value > 100 else 50  # Simplified threshold

        for item in recent:
            try:
                data = json.loads(item)
                if reading.value > 100 and data["value"] > threshold:
                    anomalous_count += 1
                elif reading.value < 50 and data["value"] < threshold:
                    anomalous_count += 1
            except (json.JSONDecodeError, KeyError):
                continue

        # Require 70% of readings to be anomalous
        return anomalous_count >= len(recent) * 0.7

    def _buffer_reading(self, reading: HRReading) -> None:
        """Buffer reading in Redis sorted set (by timestamp)."""
        key = f"{self.REDIS_KEY_PREFIX}:buffer:{reading.user_id}"

        data = json.dumps(
            {
                "value": reading.value,
                "context": reading.context.value,
                "source_provider": reading.source_provider,
                "source_device": reading.source_device,
                "medplum_patient_id": reading.medplum_patient_id,
            }
        )

        try:
            self.redis.zadd(key, {data: reading.timestamp.timestamp()})
            # Set TTL on the key
            self.redis.expire(key, self.buffer_ttl_hours * 3600)
        except redis.RedisError:
            logger.warning("Redis error buffering HR reading", exc_info=True)

    def _create_anomaly_payload(
        self,
        reading: HRReading,
        anomaly_type: str,
    ) -> dict[str, Any]:
        """Create FHIR-ready payload for anomaly alert."""
        severity = "high" if "high" in anomaly_type else "low"

        return {
            "event_type": "hr_anomaly",
            "user_id": str(reading.user_id),
            "medplum_patient_id": reading.medplum_patient_id,
            "timestamp": reading.timestamp.isoformat(),
            "data": {
                "value": reading.value,
                "unit": "beats/minute",
                "context": reading.context.value,
                "anomaly_type": anomaly_type,
                "severity": severity,
                "source": {
                    "provider": reading.source_provider,
                    "device": reading.source_device,
                },
            },
        }

    def compute_hourly_aggregation(
        self,
        user_id: UUID,
        hour_start: datetime,
    ) -> list[HRAggregation]:
        """Compute aggregations for a specific hour.

        Returns separate aggregations per context (resting, active, etc.).
        """
        key = f"{self.REDIS_KEY_PREFIX}:buffer:{user_id}"
        hour_end = hour_start + timedelta(hours=1)

        # Get all readings for the hour
        try:
            readings = self.redis.zrangebyscore(
                key,
                min=hour_start.timestamp(),
                max=hour_end.timestamp(),
            )
        except redis.RedisError:
            logger.warning("Redis error computing HR aggregation", exc_info=True)
            return []

        if not readings:
            return []

        # Group by context
        by_context: dict[HRContext, list[dict[str, Any]]] = {}
        medplum_patient_id: str | None = None

        for item in readings:
            try:
                data = json.loads(item)
                context = HRContext(data["context"])
                if context not in by_context:
                    by_context[context] = []
                by_context[context].append(data)
                medplum_patient_id = data.get("medplum_patient_id")
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

        # Compute aggregations
        aggregations = []
        for context, context_readings in by_context.items():
            values = [r["value"] for r in context_readings]

            aggregations.append(
                HRAggregation(
                    period_start=hour_start,
                    period_end=hour_end,
                    context=context,
                    min_hr=min(values),
                    max_hr=max(values),
                    avg_hr=sum(values) / len(values),
                    reading_count=len(values),
                    user_id=user_id,
                    medplum_patient_id=medplum_patient_id,
                )
            )

        return aggregations

    def create_aggregation_payload(self, agg: HRAggregation) -> dict[str, Any]:
        """Create FHIR-ready payload for hourly aggregation."""
        return {
            "event_type": "hr_hourly_summary",
            "user_id": str(agg.user_id),
            "medplum_patient_id": agg.medplum_patient_id,
            "timestamp": agg.period_end.isoformat(),
            "data": {
                "period_start": agg.period_start.isoformat(),
                "period_end": agg.period_end.isoformat(),
                "context": agg.context.value,
                "statistics": {
                    "minimum": agg.min_hr,
                    "maximum": agg.max_hr,
                    "average": round(agg.avg_hr, 1),
                    "count": agg.reading_count,
                },
                "unit": "beats/minute",
            },
        }

    def cleanup_old_data(self, user_id: UUID, before: datetime) -> int:
        """Remove buffered readings older than specified time."""
        key = f"{self.REDIS_KEY_PREFIX}:buffer:{user_id}"
        try:
            removed = self.redis.zremrangebyscore(key, 0, before.timestamp())
            return removed or 0
        except redis.RedisError:
            logger.warning("Redis error cleaning up HR data", exc_info=True)
            return 0

    def get_users_with_buffered_data(self) -> list[UUID]:
        """Get all user IDs that have buffered HR data."""
        pattern = f"{self.REDIS_KEY_PREFIX}:buffer:*"
        user_ids = []

        try:
            for key in self.redis.scan_iter(match=pattern):
                # Extract user ID from key: "medplum:hr:buffer:{user_id}"
                parts = key.split(":")
                if len(parts) >= 4:
                    try:
                        user_ids.append(UUID(parts[3]))
                    except ValueError:
                        continue
        except redis.RedisError:
            logger.warning("Redis error scanning for HR buffer keys", exc_info=True)

        return user_ids
