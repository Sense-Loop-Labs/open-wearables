"""add_clinical_action_table

Revision ID: fa1a74a0fbf3
Revises: c905ed13b9aa

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'fa1a74a0fbf3'
down_revision: Union[str, None] = 'c905ed13b9aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sl_clinical_action',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('patient_id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('practitioner_id', sa.Uuid(), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('related_alert_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['sl_organization.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['sl_patient.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['practitioner_id'], ['sl_practitioner.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sl_clinical_action_patient_id', 'sl_clinical_action', ['patient_id'], unique=False)
    op.create_index('ix_sl_clinical_action_organization_id', 'sl_clinical_action', ['organization_id'], unique=False)
    op.create_index('ix_sl_clinical_action_practitioner_id', 'sl_clinical_action', ['practitioner_id'], unique=False)
    op.create_index('ix_sl_clinical_action_created_at', 'sl_clinical_action', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_sl_clinical_action_created_at', table_name='sl_clinical_action')
    op.drop_index('ix_sl_clinical_action_practitioner_id', table_name='sl_clinical_action')
    op.drop_index('ix_sl_clinical_action_organization_id', table_name='sl_clinical_action')
    op.drop_index('ix_sl_clinical_action_patient_id', table_name='sl_clinical_action')
    op.drop_table('sl_clinical_action')
