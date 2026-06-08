"""add_cedar_access_policy_tables

Revision ID: b8c9d0e1f2a3
Revises: fa1a74a0fbf3

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "fa1a74a0fbf3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sl_access_policy table
    op.create_table(
        "sl_access_policy",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("effect", sa.String(length=50), nullable=False, server_default="permit"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_system_policy", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["sl_organization.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_access_policy_org_code"),
    )
    op.create_index("ix_sl_access_policy_organization_id", "sl_access_policy", ["organization_id"], unique=False)
    op.create_index("ix_sl_access_policy_code", "sl_access_policy", ["code"], unique=False)
    op.create_index("ix_sl_access_policy_is_active", "sl_access_policy", ["is_active"], unique=False)

    # Create sl_role_access_policy table
    op.create_table(
        "sl_role_access_policy",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("role_definition_id", sa.Uuid(), nullable=False),
        sa.Column("access_policy_id", sa.Uuid(), nullable=False),
        sa.Column("priority_override", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["role_definition_id"],
            ["sl_role_definition.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["access_policy_id"],
            ["sl_access_policy.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_definition_id", "access_policy_id", name="uq_role_access_policy"),
    )
    op.create_index("ix_sl_role_access_policy_role_definition_id", "sl_role_access_policy", ["role_definition_id"], unique=False)
    op.create_index("ix_sl_role_access_policy_access_policy_id", "sl_role_access_policy", ["access_policy_id"], unique=False)

    # Create sl_practitioner_access_policy table
    op.create_table(
        "sl_practitioner_access_policy",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("practitioner_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("access_policy_id", sa.Uuid(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("granted_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["practitioner_id"],
            ["sl_practitioner.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["sl_organization.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["access_policy_id"],
            ["sl_access_policy.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_id"],
            ["sl_practitioner.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "practitioner_id",
            "organization_id",
            "access_policy_id",
            name="uq_practitioner_access_policy",
        ),
    )
    op.create_index("ix_sl_practitioner_access_policy_practitioner_id", "sl_practitioner_access_policy", ["practitioner_id"], unique=False)
    op.create_index("ix_sl_practitioner_access_policy_organization_id", "sl_practitioner_access_policy", ["organization_id"], unique=False)
    op.create_index("ix_sl_practitioner_access_policy_access_policy_id", "sl_practitioner_access_policy", ["access_policy_id"], unique=False)
    op.create_index("ix_sl_practitioner_access_policy_valid_until", "sl_practitioner_access_policy", ["valid_until"], unique=False)

    # Create sl_break_glass_access table
    op.create_table(
        "sl_break_glass_access",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("practitioner_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("emergency_type", sa.String(length=50), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_id", sa.Uuid(), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_access_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["practitioner_id"],
            ["sl_practitioner.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["sl_organization.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_id"],
            ["sl_practitioner.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sl_break_glass_access_practitioner_id", "sl_break_glass_access", ["practitioner_id"], unique=False)
    op.create_index("ix_sl_break_glass_access_organization_id", "sl_break_glass_access", ["organization_id"], unique=False)
    op.create_index("ix_sl_break_glass_access_resource_type", "sl_break_glass_access", ["resource_type"], unique=False)
    op.create_index("ix_sl_break_glass_access_resource_id", "sl_break_glass_access", ["resource_id"], unique=False)
    op.create_index("ix_sl_break_glass_access_expires_at", "sl_break_glass_access", ["expires_at"], unique=False)
    op.create_index("ix_sl_break_glass_access_activated_at", "sl_break_glass_access", ["activated_at"], unique=False)


def downgrade() -> None:
    # Drop sl_break_glass_access table
    op.drop_index("ix_sl_break_glass_access_activated_at", table_name="sl_break_glass_access")
    op.drop_index("ix_sl_break_glass_access_expires_at", table_name="sl_break_glass_access")
    op.drop_index("ix_sl_break_glass_access_resource_id", table_name="sl_break_glass_access")
    op.drop_index("ix_sl_break_glass_access_resource_type", table_name="sl_break_glass_access")
    op.drop_index("ix_sl_break_glass_access_organization_id", table_name="sl_break_glass_access")
    op.drop_index("ix_sl_break_glass_access_practitioner_id", table_name="sl_break_glass_access")
    op.drop_table("sl_break_glass_access")

    # Drop sl_practitioner_access_policy table
    op.drop_index("ix_sl_practitioner_access_policy_valid_until", table_name="sl_practitioner_access_policy")
    op.drop_index("ix_sl_practitioner_access_policy_access_policy_id", table_name="sl_practitioner_access_policy")
    op.drop_index("ix_sl_practitioner_access_policy_organization_id", table_name="sl_practitioner_access_policy")
    op.drop_index("ix_sl_practitioner_access_policy_practitioner_id", table_name="sl_practitioner_access_policy")
    op.drop_table("sl_practitioner_access_policy")

    # Drop sl_role_access_policy table
    op.drop_index("ix_sl_role_access_policy_access_policy_id", table_name="sl_role_access_policy")
    op.drop_index("ix_sl_role_access_policy_role_definition_id", table_name="sl_role_access_policy")
    op.drop_table("sl_role_access_policy")

    # Drop sl_access_policy table
    op.drop_index("ix_sl_access_policy_is_active", table_name="sl_access_policy")
    op.drop_index("ix_sl_access_policy_code", table_name="sl_access_policy")
    op.drop_index("ix_sl_access_policy_organization_id", table_name="sl_access_policy")
    op.drop_table("sl_access_policy")
