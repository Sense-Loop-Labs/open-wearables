"""Context Detection for Heart Rate Processing.

Determines the activity context for a heart rate reading:
- Resting (no recent activity)
- Active (steps detected in recent window)
- Sleeping (within sleep session)
- Exercising (within workout session)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import DataPointSeries, DataSource, EventRecord, SeriesTypeDefinition, User
from app.services.medplum.hr_processor import HRContext

logger = logging.getLogger(__name__)


class ContextDetector:
    """Detects activity context for heart rate readings.

    Uses database queries to check for:
    - Active workout sessions (EventRecord with category='workout')
    - Sleep sessions (EventRecord with category='sleep')
    - Recent step activity (DataPointSeries with series_type='steps')
    """

    # Time window for considering recent activity
    ACTIVITY_WINDOW_MINUTES = 10

    def __init__(self, db: Session):
        self.db = db

    def detect_context(
        self,
        user_id: UUID,
        timestamp: datetime,
    ) -> HRContext:
        """Detect the activity context at a given timestamp.

        Priority order:
        1. Exercising (within active workout)
        2. Sleeping (within sleep session)
        3. Active (recent steps detected)
        4. Resting (default)
        """
        # Check for active workout
        if self._is_exercising(user_id, timestamp):
            return HRContext.EXERCISING

        # Check for sleep session
        if self._is_sleeping(user_id, timestamp):
            return HRContext.SLEEPING

        # Check for recent activity
        if self._is_active(user_id, timestamp):
            return HRContext.ACTIVE

        return HRContext.RESTING

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
        """Check if there were steps in the recent activity window."""
        window_start = timestamp - timedelta(minutes=self.ACTIVITY_WINDOW_MINUTES)

        # Get steps series type ID
        steps_type = self.db.execute(
            select(SeriesTypeDefinition).where(
                SeriesTypeDefinition.code == "steps"
            )
        ).scalar_one_or_none()

        if not steps_type:
            return False

        # Check for step readings with value > 0 in window
        result = self.db.execute(
            select(DataPointSeries)
            .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
            .where(
                and_(
                    DataSource.user_id == user_id,
                    DataPointSeries.series_type_definition_id == steps_type.id,
                    DataPointSeries.recorded_at >= window_start,
                    DataPointSeries.recorded_at <= timestamp,
                    DataPointSeries.value > 0,
                )
            ).limit(1)
        ).scalar_one_or_none()

        return result is not None

    def detect_context_batch(
        self,
        user_id: UUID,
        timestamps: list[datetime],
    ) -> dict[datetime, HRContext]:
        """Detect context for multiple timestamps efficiently.

        Optimized to reduce database queries by fetching relevant
        events and activity data in batches.
        """
        if not timestamps:
            return {}

        # Sort timestamps to determine time range
        sorted_ts = sorted(timestamps)
        start = sorted_ts[0] - timedelta(minutes=self.ACTIVITY_WINDOW_MINUTES)
        end = sorted_ts[-1]

        # Fetch all workouts in range
        workouts = self.db.execute(
            select(EventRecord)
            .join(DataSource, EventRecord.data_source_id == DataSource.id)
            .where(
                and_(
                    DataSource.user_id == user_id,
                    EventRecord.category == "workout",
                    EventRecord.start_datetime <= end,
                    EventRecord.end_datetime >= start,
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

        # Fetch steps series type
        steps_type = self.db.execute(
            select(SeriesTypeDefinition).where(
                SeriesTypeDefinition.code == "steps"
            )
        ).scalar_one_or_none()

        # Fetch all step readings in range
        steps = []
        if steps_type:
            steps = self.db.execute(
                select(DataPointSeries)
                .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
                .where(
                    and_(
                        DataSource.user_id == user_id,
                        DataPointSeries.series_type_definition_id == steps_type.id,
                        DataPointSeries.recorded_at >= start,
                        DataPointSeries.recorded_at <= end,
                        DataPointSeries.value > 0,
                    )
                )
            ).scalars().all()

        # Now determine context for each timestamp
        results: dict[datetime, HRContext] = {}

        for ts in timestamps:
            # Check workouts
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

            # Check recent steps
            window_start = ts - timedelta(minutes=self.ACTIVITY_WINDOW_MINUTES)
            has_steps = any(
                window_start <= s.recorded_at <= ts for s in steps
            )
            if has_steps:
                results[ts] = HRContext.ACTIVE
                continue

            results[ts] = HRContext.RESTING

        return results
