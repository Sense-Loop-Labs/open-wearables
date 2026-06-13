"""add_system_config_table

Revision ID: h5c6d7e8f9a0
Revises: g4b5c6d7e8f9

"""
from typing import Sequence, Union
from uuid import uuid4
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'h5c6d7e8f9a0'
down_revision: Union[str, None] = 'g4b5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Default settings
DEFAULT_SETTINGS = {
    "notifications": {
        "patient_reminder_channel": "email",
        "care_team_alert_channel": "email",
        "quiet_hours_enabled": False,
    },
    "alerts": {
        "auto_escalate": False,
        "escalation_delay_minutes": 60,
    },
}


def upgrade() -> None:
    # Drop old table if exists (from previous migration attempt)
    op.execute("DROP TABLE IF EXISTS sl_notification_config CASCADE")

    # Create the system config table
    op.create_table(
        'sl_system_config',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=True),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['sl_organization.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', name='uq_system_config_org'),
    )
    op.create_index('ix_sl_system_config_organization_id', 'sl_system_config', ['organization_id'], unique=False)

    # Seed global default config (organization_id = NULL)
    settings_json = json.dumps(DEFAULT_SETTINGS)
    op.execute(
        f"""
        INSERT INTO sl_system_config (id, organization_id, settings)
        VALUES ('{uuid4()}', NULL, '{settings_json}'::jsonb)
        """
    )


def downgrade() -> None:
    # Clean up both possible table names
    op.execute("DROP TABLE IF EXISTS sl_system_config CASCADE")
    op.execute("DROP TABLE IF EXISTS sl_notification_config CASCADE")
