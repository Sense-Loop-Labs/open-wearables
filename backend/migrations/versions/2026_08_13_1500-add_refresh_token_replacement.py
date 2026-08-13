"""Add replaced_by_id to refresh_token for grace period handling.

When a refresh token is rotated, we now track which token replaced it.
This allows recently-revoked tokens to be reused within a grace period
if the client didn't receive the new token due to network issues.

Revision ID: add_refresh_token_replacement
Revises: 71066c8e27e3
Create Date: 2026-08-13 15:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_refresh_token_replacement"
down_revision: Union[str, None] = "71066c8e27e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "refresh_token",
        sa.Column("replaced_by_id", sa.String(64), nullable=True),
    )
    # Add index for looking up replacement tokens
    op.create_index(
        "ix_refresh_token_replaced_by_id",
        "refresh_token",
        ["replaced_by_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_token_replaced_by_id", table_name="refresh_token")
    op.drop_column("refresh_token", "replaced_by_id")
