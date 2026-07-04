"""add_audit_log_immutability_trigger

Revision ID: b93071aba2c0
Revises: 8757d2c0eb1e

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b93071aba2c0'
down_revision: Union[str, None] = '8757d2c0eb1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create a function that raises an exception on UPDATE or DELETE
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'HIPAA Compliance: Audit log entries are immutable and cannot be modified or deleted. Entry ID: %', OLD.id;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger to prevent UPDATE
    op.execute("""
        CREATE TRIGGER audit_log_prevent_update
        BEFORE UPDATE ON sl_audit_log
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_log_modification();
    """)

    # Create trigger to prevent DELETE
    op.execute("""
        CREATE TRIGGER audit_log_prevent_delete
        BEFORE DELETE ON sl_audit_log
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_log_modification();
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS audit_log_prevent_update ON sl_audit_log;")
    op.execute("DROP TRIGGER IF EXISTS audit_log_prevent_delete ON sl_audit_log;")

    # Drop function
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification();")
