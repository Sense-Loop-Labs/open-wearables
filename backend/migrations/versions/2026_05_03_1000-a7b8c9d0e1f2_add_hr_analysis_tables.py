"""add hr analysis tables

SENSE-LOOP ADDITION: HR anomaly detection and hourly aggregation tables.

Revision ID: a7b8c9d0e1f2
Revises: 4bd01c907050
Create Date: 2026-05-03 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "4bd01c907050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create hr_hourly_aggregate table
    # Reduces volume from 100s of readings to 24/day by aggregating hourly
    op.create_table(
        "hr_hourly_aggregate",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("hour_start", sa.DateTime(timezone=True), nullable=False),
        # Context for the aggregation: resting, active, workout, sleep
        sa.Column("context", sa.String(length=20), nullable=False),
        # Statistics
        sa.Column("min_hr", sa.Integer(), nullable=False),
        sa.Column("max_hr", sa.Integer(), nullable=False),
        sa.Column("avg_hr", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        # Sync tracking
        sa.Column("sent_to_medplum_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # Constraints
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "hour_start", "context", name="uq_hr_hourly_user_time_context"),
    )
    op.create_index(
        "idx_hr_hourly_user_time",
        "hr_hourly_aggregate",
        ["user_id", sa.text("hour_start DESC")],
    )

    # Create hr_anomaly table
    # Only flagged readings (anomalies), not all HR data
    op.create_table(
        "hr_anomaly",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        # The anomalous heart rate
        sa.Column("heart_rate", sa.Integer(), nullable=False),
        sa.Column("context", sa.String(length=20), nullable=False),
        # Why it was flagged
        sa.Column("reason", sa.String(length=50), nullable=False),  # e.g., 'sustained_elevated_resting_hr'
        sa.Column("severity", sa.String(length=10), nullable=False),  # 'high', 'medium'
        # Comparison to baseline
        sa.Column("baseline_resting_hr", sa.Integer(), nullable=True),
        sa.Column("deviation_percent", sa.Numeric(precision=5, scale=2), nullable=True),
        # Supporting context data
        sa.Column("minutes_since_workout", sa.Integer(), nullable=True),
        sa.Column("recent_step_count", sa.Integer(), nullable=True),
        sa.Column("recent_active_energy", sa.Numeric(precision=10, scale=3), nullable=True),
        # Sync tracking
        sa.Column("sent_to_medplum_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("medplum_observation_id", sa.String(length=100), nullable=True),
        sa.Column("medplum_flag_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # Constraints
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_hr_anomaly_user_time",
        "hr_anomaly",
        ["user_id", sa.text("detected_at DESC")],
    )

    # Create hr_baseline table
    # Patient HR baseline calculated from sleep/sedentary periods
    op.create_table(
        "hr_baseline",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        # Resting HR statistics
        sa.Column("resting_hr_avg", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("resting_hr_std", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("resting_hr_min", sa.Integer(), nullable=True),
        sa.Column("resting_hr_max", sa.Integer(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=True),
        # Calculated alert threshold: resting_avg + 2*std, minimum 100
        sa.Column("elevated_threshold", sa.Integer(), nullable=True),
        # Timestamps
        sa.Column("last_calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # Constraints
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_hr_baseline_user"),
    )


def downgrade() -> None:
    op.drop_table("hr_baseline")
    op.drop_index("idx_hr_anomaly_user_time", table_name="hr_anomaly")
    op.drop_table("hr_anomaly")
    op.drop_index("idx_hr_hourly_user_time", table_name="hr_hourly_aggregate")
    op.drop_table("hr_hourly_aggregate")
