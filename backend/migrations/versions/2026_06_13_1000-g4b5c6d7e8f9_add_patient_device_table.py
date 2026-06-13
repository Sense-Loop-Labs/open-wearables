"""add_patient_device_table

Revision ID: g4b5c6d7e8f9
Revises: f3a4b5c6d7e8

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g4b5c6d7e8f9'
down_revision: Union[str, None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sl_patient_device',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('patient_id', sa.Uuid(), nullable=False),
        sa.Column('device_token', sa.Text(), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False, server_default='ios'),
        sa.Column('device_name', sa.String(length=255), nullable=True),
        sa.Column('app_version', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['patient_id'], ['sl_patient.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('device_token'),
    )
    op.create_index('ix_sl_patient_device_patient_id', 'sl_patient_device', ['patient_id'], unique=False)
    op.create_index('ix_sl_patient_device_is_active', 'sl_patient_device', ['is_active'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_sl_patient_device_is_active', table_name='sl_patient_device')
    op.drop_index('ix_sl_patient_device_patient_id', table_name='sl_patient_device')
    op.drop_table('sl_patient_device')
