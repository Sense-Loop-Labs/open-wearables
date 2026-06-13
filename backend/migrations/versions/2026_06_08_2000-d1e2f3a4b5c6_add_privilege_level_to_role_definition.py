"""add_privilege_level_to_role_definition

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b4

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Privilege levels for existing roles
ROLE_PRIVILEGE_LEVELS = {
    'super_admin': 100,
    'org_admin': 80,
    'doctor': 60,
    'physician_assistant': 55,
    'nurse_practitioner': 55,
    'nurse': 50,
    'care_coordinator': 45,
    'medical_assistant': 40,
    'readonly': 10,
}


def upgrade() -> None:
    # Add the column with a default value
    op.add_column(
        'sl_role_definition',
        sa.Column('privilege_level', sa.Integer(), nullable=False, server_default='50')
    )

    # Update existing roles with appropriate privilege levels
    for role_code, level in ROLE_PRIVILEGE_LEVELS.items():
        op.execute(
            sa.text(
                "UPDATE sl_role_definition SET privilege_level = :level WHERE code = :code"
            ).bindparams(level=level, code=role_code)
        )

    # Remove the server default (optional, keeps table cleaner)
    op.alter_column('sl_role_definition', 'privilege_level', server_default=None)


def downgrade() -> None:
    op.drop_column('sl_role_definition', 'privilege_level')
