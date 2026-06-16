"""Add patient questionnaire assignment table

Revision ID: 252d68aafec6
Revises: i6d7e8f9a0b1

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '252d68aafec6'
down_revision: Union[str, None] = 'i6d7e8f9a0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('sl_patient_questionnaire_assignment',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('patient_id', sa.UUID(), nullable=False),
        sa.Column('questionnaire_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('effective_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('effective_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('assigned_by_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['assigned_by_id'], ['sl_practitioner.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['patient_id'], ['sl_patient.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['questionnaire_id'], ['sl_questionnaire.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_sl_patient_questionnaire_assignment_patient_id'),
        'sl_patient_questionnaire_assignment',
        ['patient_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_sl_patient_questionnaire_assignment_questionnaire_id'),
        'sl_patient_questionnaire_assignment',
        ['questionnaire_id'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_sl_patient_questionnaire_assignment_questionnaire_id'),
        table_name='sl_patient_questionnaire_assignment'
    )
    op.drop_index(
        op.f('ix_sl_patient_questionnaire_assignment_patient_id'),
        table_name='sl_patient_questionnaire_assignment'
    )
    op.drop_table('sl_patient_questionnaire_assignment')
