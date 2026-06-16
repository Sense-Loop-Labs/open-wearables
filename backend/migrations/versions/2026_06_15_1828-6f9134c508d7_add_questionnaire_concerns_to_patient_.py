"""add_questionnaire_concerns_to_patient_summary

Revision ID: 6f9134c508d7
Revises: 252d68aafec6

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6f9134c508d7'
down_revision: Union[str, None] = '252d68aafec6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sl_patient_summary', sa.Column('has_questionnaire_concerns', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('sl_patient_summary', sa.Column('questionnaire_concern_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('sl_patient_summary', sa.Column('highest_questionnaire_severity', sa.String(50), nullable=True))
    op.add_column('sl_patient_summary', sa.Column('questionnaire_concerns', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('sl_patient_summary', sa.Column('last_questionnaire_response_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('sl_patient_summary', 'last_questionnaire_response_at')
    op.drop_column('sl_patient_summary', 'questionnaire_concerns')
    op.drop_column('sl_patient_summary', 'highest_questionnaire_severity')
    op.drop_column('sl_patient_summary', 'questionnaire_concern_count')
    op.drop_column('sl_patient_summary', 'has_questionnaire_concerns')
