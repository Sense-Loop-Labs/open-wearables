"""HR Analysis Models for context-aware heart rate monitoring.

SENSE-LOOP ADDITION: This entire module is a Sense Loop addition.

These models support:
- Hourly HR aggregation to reduce data volume
- Anomaly detection and storage
- Per-patient HR baselines for personalized thresholds
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseDbModel
from app.mappings import FKUser, PrimaryKey, numeric_5_2, numeric_10_3, str_10, str_50, str_100


class HRHourlyAggregate(BaseDbModel):
    """Hourly heart rate aggregation to reduce data volume.

    Groups HR readings by hour and context (resting, active, workout, sleep).
    Reduces ~100s of readings per day to ~24 aggregated records.
    """

    __tablename__ = "hr_hourly_aggregate"

    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]
    hour_start: Mapped[datetime]

    # Context for this aggregation period
    context: Mapped[str] = mapped_column(nullable=False)  # resting, active, workout, sleep, post_workout

    # Statistics for the hour
    min_hr: Mapped[int]
    max_hr: Mapped[int]
    avg_hr: Mapped[numeric_5_2]
    sample_count: Mapped[int]

    # Sync tracking
    sent_to_medplum_at: Mapped[datetime | None]


class HRAnomaly(BaseDbModel):
    """Detected HR anomaly record.

    Only stores flagged readings that meet anomaly criteria:
    - Elevated HR while sedentary
    - Sustained elevation (5+ minutes)
    - Deviation from baseline
    """

    __tablename__ = "hr_anomaly"

    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]
    detected_at: Mapped[datetime]

    # The anomalous reading
    heart_rate: Mapped[int]
    context: Mapped[str] = mapped_column(nullable=False)  # resting, active, sleeping, etc.

    # Classification
    reason: Mapped[str_50]  # e.g., 'sustained_elevated_resting_hr', 'slow_recovery', 'elevated_sleep'
    severity: Mapped[str_10]  # 'high', 'medium'

    # Comparison to baseline (if available)
    baseline_resting_hr: Mapped[int | None]
    deviation_percent: Mapped[numeric_5_2 | None]

    # Supporting context data captured at detection time
    minutes_since_workout: Mapped[int | None]
    recent_step_count: Mapped[int | None]
    recent_active_energy: Mapped[numeric_10_3 | None]

    # Medplum sync tracking
    sent_to_medplum_at: Mapped[datetime | None]
    medplum_observation_id: Mapped[str_100 | None]
    medplum_flag_id: Mapped[str_100 | None]


class HRBaseline(BaseDbModel):
    """Patient-specific HR baseline calculated from sleep/sedentary periods.

    Used to personalize alert thresholds based on individual physiology.
    Recalculated nightly from the previous 7-14 days of resting HR data.
    """

    __tablename__ = "hr_baseline"

    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]

    # Resting HR statistics (from sleep/sedentary periods)
    resting_hr_avg: Mapped[numeric_5_2 | None]
    resting_hr_std: Mapped[numeric_5_2 | None]
    resting_hr_min: Mapped[int | None]
    resting_hr_max: Mapped[int | None]
    sample_count: Mapped[int | None]

    # Calculated alert threshold: max(resting_avg + 2*std, 100)
    elevated_threshold: Mapped[int | None]

    # When baseline was last calculated
    last_calculated_at: Mapped[datetime | None]
    updated_at: Mapped[datetime]
