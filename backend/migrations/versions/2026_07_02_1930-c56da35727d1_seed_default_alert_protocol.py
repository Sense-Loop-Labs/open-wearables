"""Seed default alert protocol for vital sign monitoring.

This migration creates the system-wide default alert protocol used by the
alert engine to evaluate vital signs and generate alerts. Without this
protocol, no vital sign alerts will be created.

The protocol includes rules for:
- Temperature (fever detection)
- Heart rate (tachycardia/bradycardia)
- SpO2 (hypoxemia)
- Blood pressure systolic (hypertension/hypotension)
- Blood pressure diastolic (hypertension/hypotension)

This migration is idempotent - it only inserts missing data.

Revision ID: c56da35727d1
Revises: 6fb04ed2dfb7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c56da35727d1"
down_revision: Union[str, None] = "6fb04ed2dfb7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Fixed UUIDs for predictable seeding (idempotent)
PROTOCOL_ID = "a0000001-0000-0000-0000-000000000001"
RISK_WINDOW_ID = "c0000001-0000-0000-0000-000000000001"

# Alert protocol rules with thresholds based on clinical guidelines
ALERT_RULES = [
    {
        "id": "b0000001-0000-0000-0000-000000000001",
        "code": "TEMP",
        "name": "Temperature",
        "vital_type": "temperature",
        "high_warning": 100.4,  # 38°C - low-grade fever
        "high_critical": 101.5,  # 38.6°C - significant fever
        "low_warning": 96.0,  # 35.6°C - mild hypothermia
        "low_critical": 95.0,  # 35°C - hypothermia
    },
    {
        "id": "b0000002-0000-0000-0000-000000000001",
        "code": "HR",
        "name": "Heart Rate",
        "vital_type": "heart_rate",
        "high_warning": 100,  # Tachycardia threshold
        "high_critical": 120,  # Significant tachycardia
        "low_warning": 50,  # Bradycardia threshold
        "low_critical": 40,  # Significant bradycardia
    },
    {
        "id": "b0000003-0000-0000-0000-000000000001",
        "code": "SPO2",
        "name": "SpO2",
        "vital_type": "spo2",
        "high_warning": None,
        "high_critical": None,
        "low_warning": 94,  # Mild hypoxemia
        "low_critical": 90,  # Significant hypoxemia
    },
    {
        "id": "b0000004-0000-0000-0000-000000000001",
        "code": "BP_SYS",
        "name": "Blood Pressure Systolic",
        "vital_type": "blood_pressure_systolic",
        "high_warning": 160,  # Stage 2 hypertension
        "high_critical": 180,  # Hypertensive crisis
        "low_warning": 90,  # Hypotension
        "low_critical": 80,  # Significant hypotension
    },
    {
        "id": "b0000005-0000-0000-0000-000000000001",
        "code": "BP_DIA",
        "name": "Blood Pressure Diastolic",
        "vital_type": "blood_pressure_diastolic",
        "high_warning": 100,  # Stage 2 hypertension
        "high_critical": 120,  # Hypertensive crisis
        "low_warning": 60,  # Hypotension
        "low_critical": 50,  # Significant hypotension
    },
]


def upgrade() -> None:
    # Insert default alert protocol (system-wide, organization_id = NULL)
    op.execute(
        sa.text("""
            INSERT INTO sl_alert_protocol (
                id, name, code, version, description,
                organization_id, status, created_at, published_at
            )
            VALUES (
                CAST(:id AS uuid), :name, :code, :version, :description,
                NULL, 'published', now(), now()
            )
            ON CONFLICT (id) DO NOTHING
        """).bindparams(
            id=PROTOCOL_ID,
            name="Default Post-Operative Monitoring",
            code="DEFAULT_POST_OP",
            version=1,
            description="System-wide default protocol for post-operative vital sign monitoring. "
                       "Provides baseline thresholds for detecting abnormal vital signs.",
        )
    )

    # Insert alert rules
    for idx, rule in enumerate(ALERT_RULES):
        op.execute(
            sa.text("""
                INSERT INTO sl_alert_protocol_rule (
                    id, protocol_id, code, name, vital_type,
                    high_warning, high_critical, low_warning, low_critical,
                    priority, is_active, alert_severity, cooldown_minutes,
                    notify_patient, notify_care_team, created_at
                )
                VALUES (
                    CAST(:id AS uuid), CAST(:protocol_id AS uuid), :code, :name, :vital_type,
                    :high_warning, :high_critical, :low_warning, :low_critical,
                    :priority, true, 'critical', 60,
                    false, true, now()
                )
                ON CONFLICT (id) DO NOTHING
            """).bindparams(
                id=rule["id"],
                protocol_id=PROTOCOL_ID,
                code=rule["code"],
                name=rule["name"],
                vital_type=rule["vital_type"],
                high_warning=rule["high_warning"],
                high_critical=rule["high_critical"],
                low_warning=rule["low_warning"],
                low_critical=rule["low_critical"],
                priority=idx + 1,
            )
        )

    # Insert default risk window (covers days 0-90 post-surgery)
    op.execute(
        sa.text("""
            INSERT INTO sl_alert_risk_window (
                id, protocol_id, name, start_day, end_day,
                risk_level, description, created_at
            )
            VALUES (
                CAST(:id AS uuid), CAST(:protocol_id AS uuid), :name, :start_day, :end_day,
                :risk_level, :description, now()
            )
            ON CONFLICT (id) DO NOTHING
        """).bindparams(
            id=RISK_WINDOW_ID,
            protocol_id=PROTOCOL_ID,
            name="Standard Recovery",
            start_day=0,
            end_day=90,
            risk_level="high",
            description="Standard post-operative recovery window with elevated monitoring.",
        )
    )


def downgrade() -> None:
    # Delete risk window
    op.execute(
        sa.text("DELETE FROM sl_alert_risk_window WHERE id = CAST(:id AS uuid)").bindparams(
            id=RISK_WINDOW_ID
        )
    )

    # Delete alert rules
    for rule in ALERT_RULES:
        op.execute(
            sa.text("DELETE FROM sl_alert_protocol_rule WHERE id = CAST(:id AS uuid)").bindparams(
                id=rule["id"]
            )
        )

    # Delete protocol
    op.execute(
        sa.text("DELETE FROM sl_alert_protocol WHERE id = CAST(:id AS uuid)").bindparams(
            id=PROTOCOL_ID
        )
    )
