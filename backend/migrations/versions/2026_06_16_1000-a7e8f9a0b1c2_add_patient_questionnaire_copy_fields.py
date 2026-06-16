"""add_patient_questionnaire_copy_fields

Revision ID: a7e8f9a0b1c2
Revises: 6f9134c508d7

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a7e8f9a0b1c2'
down_revision: Union[str, None] = '6f9134c508d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add patient_id column - links questionnaire to a specific patient (null = template)
    op.add_column(
        'sl_questionnaire',
        sa.Column(
            'patient_id',
            sa.UUID(),
            sa.ForeignKey('sl_patient.id', ondelete='CASCADE'),
            nullable=True,
        )
    )
    op.create_index(
        'ix_sl_questionnaire_patient_id',
        'sl_questionnaire',
        ['patient_id'],
    )

    # Add source_template_id column - tracks which template was copied
    op.add_column(
        'sl_questionnaire',
        sa.Column(
            'source_template_id',
            sa.UUID(),
            sa.ForeignKey('sl_questionnaire.id', ondelete='SET NULL'),
            nullable=True,
        )
    )


def downgrade() -> None:
    op.drop_column('sl_questionnaire', 'source_template_id')
    op.drop_index('ix_sl_questionnaire_patient_id', table_name='sl_questionnaire')
    op.drop_column('sl_questionnaire', 'patient_id')
