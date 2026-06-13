"""add_timezone_to_organization

Revision ID: i6d7e8f9a0b1
Revises: h5c6d7e8f9a0

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i6d7e8f9a0b1'
down_revision: Union[str, None] = 'h5c6d7e8f9a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add default_timezone to organization
    op.add_column(
        'sl_organization',
        sa.Column('default_timezone', sa.String(length=100), nullable=False, server_default='America/Los_Angeles')
    )

    # Rename timezone to timezone_override in patient and make nullable
    op.alter_column(
        'sl_patient',
        'timezone',
        new_column_name='timezone_override',
        nullable=True,
    )

    # Set existing patient timezones to NULL so they inherit from org
    # (keeping any that were explicitly set different from the old default)
    op.execute("""
        UPDATE sl_patient
        SET timezone_override = NULL
        WHERE timezone_override = 'America/New_York'
    """)


def downgrade() -> None:
    # Restore timezone column name and make non-nullable with default
    op.execute("""
        UPDATE sl_patient
        SET timezone_override = 'America/New_York'
        WHERE timezone_override IS NULL
    """)

    op.alter_column(
        'sl_patient',
        'timezone_override',
        new_column_name='timezone',
        nullable=False,
        server_default='America/Los_Angeles',
    )

    op.drop_column('sl_organization', 'default_timezone')
