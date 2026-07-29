"""add_patient_password_reset_fields

Revision ID: 71066c8e27e3
Revises: b93071aba2c0

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71066c8e27e3'
down_revision: Union[str, None] = 'b93071aba2c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add password reset fields to patient table
    op.add_column(
        'sl_patient',
        sa.Column('password_reset_token', sa.String(255), nullable=True)
    )
    op.add_column(
        'sl_patient',
        sa.Column('password_reset_expires_at', sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('sl_patient', 'password_reset_expires_at')
    op.drop_column('sl_patient', 'password_reset_token')
