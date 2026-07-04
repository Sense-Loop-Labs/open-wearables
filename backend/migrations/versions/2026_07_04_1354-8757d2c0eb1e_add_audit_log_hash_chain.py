"""add_audit_log_hash_chain

Revision ID: 8757d2c0eb1e
Revises: c56da35727d1

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8757d2c0eb1e'
down_revision: Union[str, None] = 'c56da35727d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add hash chain columns for tamper-evident audit log
    op.add_column(
        'sl_audit_log',
        sa.Column('entry_hash', sa.String(255), nullable=True)
    )
    op.add_column(
        'sl_audit_log',
        sa.Column('previous_hash', sa.String(255), nullable=True)
    )
    op.add_column(
        'sl_audit_log',
        sa.Column('sequence_number', sa.BigInteger(), nullable=True)
    )

    # Add indexes for efficient verification queries
    op.create_index('ix_sl_audit_log_entry_hash', 'sl_audit_log', ['entry_hash'])
    op.create_index('ix_sl_audit_log_sequence_number', 'sl_audit_log', ['sequence_number'])


def downgrade() -> None:
    op.drop_index('ix_sl_audit_log_sequence_number', table_name='sl_audit_log')
    op.drop_index('ix_sl_audit_log_entry_hash', table_name='sl_audit_log')
    op.drop_column('sl_audit_log', 'sequence_number')
    op.drop_column('sl_audit_log', 'previous_hash')
    op.drop_column('sl_audit_log', 'entry_hash')
