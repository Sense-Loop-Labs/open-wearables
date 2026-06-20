"""add_value_set_tables

Revision ID: dc73cceb7f66
Revises: 957da397ab9e

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'dc73cceb7f66'
down_revision: Union[str, None] = '957da397ab9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sl_value_set table
    op.create_table(
        'sl_value_set',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('code', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('organization_id', sa.UUID(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['sl_organization.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', 'organization_id', name='uq_value_set_code_org')
    )
    op.create_index(op.f('ix_sl_value_set_code'), 'sl_value_set', ['code'], unique=False)
    op.create_index(op.f('ix_sl_value_set_organization_id'), 'sl_value_set', ['organization_id'], unique=False)

    # Create sl_value_set_item table
    op.create_table(
        'sl_value_set_item',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('value_set_id', sa.UUID(), nullable=False),
        sa.Column('code', sa.String(length=100), nullable=False),
        sa.Column('display', sa.String(length=255), nullable=False),
        sa.Column('coding_system', sa.String(length=255), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('extra_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['value_set_id'], ['sl_value_set.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('value_set_id', 'code', name='uq_value_set_item_code')
    )
    op.create_index(op.f('ix_sl_value_set_item_value_set_id'), 'sl_value_set_item', ['value_set_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sl_value_set_item_value_set_id'), table_name='sl_value_set_item')
    op.drop_table('sl_value_set_item')
    op.drop_index(op.f('ix_sl_value_set_organization_id'), table_name='sl_value_set')
    op.drop_index(op.f('ix_sl_value_set_code'), table_name='sl_value_set')
    op.drop_table('sl_value_set')
