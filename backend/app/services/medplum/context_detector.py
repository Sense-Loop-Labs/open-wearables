"""Context Detection for Heart Rate Processing.

SENSE-LOOP ADDITION: This entire module is a Sense Loop addition for context-aware HR processing.

Determines the activity context for a heart rate reading:
- Resting (no recent activity)
- Active (steps OR active energy detected in recent window)
- Sleeping (within sleep session)
- Exercising (within workout session)
- Post-workout (recovery period after workout ends)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import DataPointSeries, DataSource, EventRecord, SeriesTypeDefinition, User
from app.services.medplum.hr_processor import HRContext

logger = logging.getLogger(__name__)


class ContextDetector:
    """Detects activity context for heart rate readings.

    Uses database queries to check for:
    - Active workout sessions (EventRecord with category='workout')
    - Sleep sessions (EventRecord with category='sleep')
    - Recent step activity (DataPointSeries with series_type='steps')
    - Recent active energy (DataPointSeries with series_type='energy')
    """

    # Time window for considering recent activity
    ACTIVITY_WINDOW_MINUTES = 10

    # Cache for series type definition IDs (static data)
    _series_type_cache: dict[str, int] = {}

    def __init__(self, db: Session):
        self.db = db
        self._steps_type_id: int | None = None
        self._energy_type_id: int | None = None

    def _get_series_type_id(self, code: str) -> int | None:
        """Get series type ID with caching to avoid repeated lookups."""
        # Check instance cache first
        if code == "steps" and self._steps_type_id is not None:
            return self._steps_type_id
        if code == "energy" and self._energy_type_id is not None:
            return self._energy_type_id

        # Check class-level cache
        if code in ContextDetector._series_type_cache:
            type_id = ContextDetector._series_type_cache[code]
            if code == "steps":
                self._steps_type_id = type_id
            elif code == "energy":
                self._energy_type_id = type_id
            return type_id

        # Query database
        series_type = self.db.execute(
            select(SeriesTypeDefinition).where(
                SeriesTypeDefinition.code == code
            )
        ).scalar_one_or_none()

        if series_type:
            type_id = series_type.id
            ContextDetector._series_type_cache[code] = type_id
            if code == "steps":
                self._steps_type_id = type_id
            elif code == "energy":
                self._energy_type_id = type_id
            return type_id

        return None

    def detect_context(
        self,
        user_id: UUID,
        timestamp: datetime,
    ) -> HRContext:
        """Detect the activity context at a given timestamp.

        Priority order:
        1. Exercising (within active workout)
        2. Sleeping (within sleep session)
        3. Post-workout (recovery period after workout ended)
        4. Active (recent steps OR active energy detected)
        5. Resting (default)
        """
        # Check for active workout
        if self._is_exercising(user_id, timestamp):
            return HRContext.EXERCISING

        # Check for sleep session
        if self._is_sleeping(user_id, timestamp):
            return HRContext.SLEEPING

        # Check for post-workout recovery period
        minutes_since = self._get_minutes_since_workout(user_id, timestamp)
        if minutes_since is not None and minutes_since < settings.hr_post_workout_recovery_minutes:
            return HRContext.POST_WORKOUT

        # Check for recent activity (steps OR active energy)
        if self._is_active(user_id, timestamp):
            return HRContext.ACTIVE

        return HRContext.RESTING

    def get_minutes_since_workout(self, user_id: UUID, timestamp: datetime) -> int | None:
        """Public method to get minutes since last workout for context data."""
        return self._get_minutes_since_workout(user_id, timestamp)

    def get_recent_steps(self, user_id: UUID, timestamp: datetime) -> int:
        """Get total steps in the activity window."""
        return self._get_recent_step_count(user_id, timestamp)

    def get_recent_energy(self, user_id: UUID, timestamp: datetime) -> Decimal:
        """Get total active energy in the activity window."""
        return self._get_recent_active_energy(user_id, timestamp)

    def _is_exercising(self, user_id: UUID, timestamp: datetime) -> bool:
        """Check if timestamp falls within an active workout."""
        # Check for workout event that contains this timestamp
        result = self.db.execute(
            select(EventRecord)
            .join(DataSource, EventRecord.data_source_id == DataSource.id)
            .where(
                and_(
                    DataSource.user_id == user_id,
                    EventRecord.category == "workout",
                    EventRecord.start_datetime <= timestamp,
                    EventRecord.end_datetime >= timestamp,
                )
            )
        ).scalar_one_or_none()

        return result is not None

    def _is_sleeping(self, user_id: UUID, timestamp: datetime) -> bool:
        """Check if timestamp falls within a sleep session."""
        result = self.db.execute(
            select(EventRecord)
            .join(DataSource, EventRecord.data_source_id == DataSource.id)
            .where(
                and_(
                    DataSource.user_id == user_id,
                    EventRecord.category == "sleep",
                    EventRecord.start_datetime <= timestamp,
                    EventRecord.end_datetime >= timestamp,
                )
            )
        ).scalar_one_or_none()

        return result is not None

    def _is_active(self, user_id: UUID, timestamp: datetime) -> bool:
        """Check if user is active via steps OR active energy.

        A user is considered active if in the last 10 minutes:
        - Steps > 100, OR
        - Active energy burned > threshold (default 40 kcal)

        This catches stationary exercise like biking or rowing that
        burn energy without taking steps.
        """
        # Check steps first (more common)
        if self._has_recent_steps(user_id, timestamp):
            return True

        # Check active energy (catches stationary exercise)
        if self._has_recent_active_energy(user_id, timestamp):
            return True

        return False

    def _has_recent_steps(self, user_id: UUID, timestamp: datetime, threshold: int = 100) -> bool:
        """Check if total steps in window exceeds threshold."""
        step_count = self._get_recent_step_count(user_id, timestamp)
        return step_count > threshold

    def _get_recent_step_count(self, user_id: UUID, timestamp: datetime) -> int:
        """Get total step count in the activity window."""
        window_start = timestamp - timedelta(minutes=self.ACTIVITY_WINDOW_MINUTES)

        # Get steps series type ID (cached)
        steps_type_id = self._get_series_type_id("steps")
        if not steps_type_id:
            return 0

        # Sum steps in window
        result = self.db.execute(
            select(func.coalesce(func.sum(DataPointSeries.value), 0))
            .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
            .where(
                and_(
                    DataSource.user_id == user_id,
                    DataPointSeries.series_type_definition_id == steps_type_id,
                    DataPointSeries.recorded_at >= window_start,
                    DataPointSeries.recorded_at <= timestamp,
                )
            )
        ).scalar()

        return int(result or 0)

    def _has_recent_active_energy(
        self,
        user_id: UUID,
        timestamp: datetime,
        threshold_kcal: float | None = None,
    ) -> bool:
        """Check if active energy burned exceeds threshold in activity window.

        This catches stationary exercise like biking, rowing, or elliptical
        that burn calories without taking many steps.
        """
        threshold = threshold_kcal or settings.hr_active_energy_threshold_kcal
        energy = self._get_recent_active_energy(user_id, timestamp)
        return float(energy) > threshold

    def _get_recent_active_energy(self, user_id: UUID, timestamp: datetime) -> Decimal:
        """Get total active energy burned in the activity window."""
        window_start = timestamp - timedelta(minutes=self.ACTIVITY_WINDOW_MINUTES)

        # Get energy series type ID (cached)
        energy_type_id = self._get_series_type_id("energy")
        if not energy_type_id:
            return Decimal(0)

        # Sum active energy in window
        result = self.db.execute(
            select(func.coalesce(func.sum(DataPointSeries.value), 0))
            .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
            .where(
                and_(
                    DataSource.user_id == user_id,
                    DataPointSeries.series_type_definition_id == energy_type_id,
                    DataPointSeries.recorded_at >= window_start,
                    DataPointSeries.recorded_at <= timestamp,
                )
            )
        ).scalar()

        return Decimal(str(result or 0))

    def _get_minutes_since_workout(self, user_id: UUID, timestamp: datetime) -> int | None:
        """Get minutes since last workout ended, or None if no recent workout.

        Looks back up to 2 hours for a completed workout.
        """
        lookback_start = timestamp - timedelta(hours=2)

        # Find the most recent workout that ended before this timestamp
        last_workout = self.db.execute(
            select(EventRecord)
            .join(DataSource, EventRecord.data_source_id == DataSource.id)
            .where(
                and_(
                    DataSource.user_id == user_id,
                    EventRecord.category == "workout",
                    EventRecord.end_datetime < timestamp,
                    EventRecord.end_datetime > lookback_start,
                )
            )
            .order_by(EventRecord.end_datetime.desc())
        ).scalar_one_or_none()

        if last_workout and last_workout.end_datetime:
            delta = timestamp - last_workout.end_datetime
            return int(delta.total_seconds() / 60)

        return None

    def detect_context_batch(
        self,
        user_id: UUID,
        timestamps: list[datetime],
    ) -> dict[datetime, HRContext]:
        """Detect context for multiple timestamps efficiently.

        Optimized to reduce database queries by fetching relevant
        events and activity data in batches.

        Priority order:
        1. Exercising (within active workout)
        2. Sleeping (within sleep session)
        3. Post-workout (recovery period after workout ended)
        4. Active (recent steps OR active energy)
        5. Resting (default)
        """
        if not timestamps:
            return {}

        # Sort timestamps to determine time range
        sorted_ts = sorted(timestamps)
        start = sorted_ts[0] - timedelta(minutes=self.ACTIVITY_WINDOW_MINUTES)
        end = sorted_ts[-1]
        # Extended start for post-workout lookback
        extended_start = sorted_ts[0] - timedelta(hours=2)

        # Fetch all workouts in range (including those that ended recently for post-workout)
        workouts = self.db.execute(
            select(EventRecord)
            .join(DataSource, EventRecord.data_source_id == DataSource.id)
            .where(
                and_(
                    DataSource.user_id == user_id,
                    EventRecord.category == "workout",
                    EventRecord.end_datetime >= extended_start,
                    EventRecord.start_datetime <= end,
                )
            )
        ).scalars().all()

        # Fetch all sleep sessions in range
        sleeps = self.db.execute(
            select(EventRecord)
            .join(DataSource, EventRecord.data_source_id == DataSource.id)
            .where(
                and_(
                    DataSource.user_id == user_id,
                    EventRecord.category == "sleep",
                    EventRecord.start_datetime <= end,
                    EventRecord.end_datetime >= start,
                )
            )
        ).scalars().all()

        # Get series type IDs (cached)
        steps_type_id = self._get_series_type_id("steps")
        energy_type_id = self._get_series_type_id("energy")

        # Fetch all step readings in range
        steps = []
        if steps_type_id:
            steps = self.db.execute(
                select(DataPointSeries)
                .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
                .where(
                    and_(
                        DataSource.user_id == user_id,
                        DataPointSeries.series_type_definition_id == steps_type_id,
                        DataPointSeries.recorded_at >= start,
                        DataPointSeries.recorded_at <= end,
                        DataPointSeries.value > 0,
                    )
                )
            ).scalars().all()

        # Fetch all energy readings in range
        energy_readings = []
        if energy_type_id:
            energy_readings = self.db.execute(
                select(DataPointSeries)
                .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
                .where(
                    and_(
                        DataSource.user_id == user_id,
                        DataPointSeries.series_type_definition_id == energy_type_id,
                        DataPointSeries.recorded_at >= start,
                        DataPointSeries.recorded_at <= end,
                        DataPointSeries.value > 0,
                    )
                )
            ).scalars().all()

        recovery_minutes = settings.hr_post_workout_recovery_minutes
        energy_threshold = settings.hr_active_energy_threshold_kcal

        # Now determine context for each timestamp
        results: dict[datetime, HRContext] = {}

        for ts in timestamps:
            # Check if currently in workout
            in_workout = any(
                w.start_datetime <= ts <= w.end_datetime for w in workouts
            )
            if in_workout:
                results[ts] = HRContext.EXERCISING
                continue

            # Check sleep
            in_sleep = any(
                s.start_datetime <= ts <= s.end_datetime for s in sleeps
            )
            if in_sleep:
                results[ts] = HRContext.SLEEPING
                continue

            # Check post-workout recovery
            recent_workout_end = None
            for w in workouts:
                if w.end_datetime and w.end_datetime < ts:
                    if recent_workout_end is None or w.end_datetime > recent_workout_end:
                        recent_workout_end = w.end_datetime

            if recent_workout_end:
                minutes_since = (ts - recent_workout_end).total_seconds() / 60
                if minutes_since < recovery_minutes:
                    results[ts] = HRContext.POST_WORKOUT
                    continue

            # Check recent steps
            window_start = ts - timedelta(minutes=self.ACTIVITY_WINDOW_MINUTES)
            step_sum = sum(
                float(s.value) for s in steps
                if window_start <= s.recorded_at <= ts
            )
            if step_sum > 100:
                results[ts] = HRContext.ACTIVE
                continue

            # Check recent active energy
            energy_sum = sum(
                float(e.value) for e in energy_readings
                if window_start <= e.recorded_at <= ts
            )
            if energy_sum > energy_threshold:
                results[ts] = HRContext.ACTIVE
                continue

            results[ts] = HRContext.RESTING

        return results
