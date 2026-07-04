"""Audit log model - HIPAA audit trail (immutable)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_50, str_100, str_255


class AuditLog(BaseDbModel):
    """HIPAA audit trail entry (immutable).

    Every PHI access is logged with:
    - WHO: actor_type, actor_id, actor_name, organization_id
    - WHAT: action, resource_type, resource_id
    - WHEN: timestamp
    - WHY: endpoint, http_method, request_id
    - OUTCOME: success/failure/denied
    """

    __tablename__ = "sl_audit_log"

    id: Mapped[PrimaryKey[UUID]]

    # WHO - Actor identification
    actor_type: Mapped[str_50]  # practitioner, patient, system, api_key
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    actor_name: Mapped[str_255 | None] = mapped_column(nullable=True)
    actor_email: Mapped[str_255 | None] = mapped_column(nullable=True)

    # Organization context
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_organization.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # WHAT - Action and resource
    action: Mapped[str_100]  # create, read, update, delete, export, login, logout, etc.
    resource_type: Mapped[str_100]  # patient, alert, care_plan, etc.
    resource_id: Mapped[UUID | None] = mapped_column(nullable=True)
    resource_name: Mapped[str_255 | None] = mapped_column(nullable=True)

    # WHEN - Timestamp (use created_at from BaseDbModel)

    # WHY - Request context
    endpoint: Mapped[str_255 | None] = mapped_column(nullable=True)
    http_method: Mapped[str_50 | None] = mapped_column(nullable=True)
    request_id: Mapped[str_100 | None] = mapped_column(nullable=True, index=True)

    # Request details
    ip_address: Mapped[str_50 | None] = mapped_column(nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # OUTCOME
    outcome: Mapped[str_50]  # success, failure, denied
    outcome_reason: Mapped[str_255 | None] = mapped_column(nullable=True)

    # Additional context
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # For storing additional context like:
    # - Fields accessed/modified
    # - Query parameters
    # - Old/new values for updates
    # - Export format and filters

    # PHI fields accessed (for compliance reporting)
    phi_fields_accessed: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # ['name', 'dob', 'phone', 'email', 'address', 'medical_history']

    # Changes made (for update operations)
    changes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # {"field": {"old": "...", "new": "..."}}

    # Hash chain for integrity verification (HIPAA tamper-evidence)
    entry_hash: Mapped[str_255 | None] = mapped_column(nullable=True, index=True)
    # SHA-256 hash of this entry's key fields + previous_hash
    previous_hash: Mapped[str_255 | None] = mapped_column(nullable=True)
    # Hash of the previous entry in the chain (NULL for first entry)
    sequence_number: Mapped[int | None] = mapped_column(nullable=True, index=True)
    # Sequential counter for ordering and gap detection

    # Note: This table should NEVER have UPDATE or DELETE operations
    # All entries are immutable for compliance


# Common audit actions
class AuditAction:
    """Constants for audit actions."""

    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_RESET = "password_reset"
    PASSWORD_CHANGE = "password_change"

    # CRUD operations
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"

    # Clinical actions
    ACKNOWLEDGE_ALERT = "acknowledge_alert"
    RESOLVE_ALERT = "resolve_alert"
    ESCALATE_ALERT = "escalate_alert"

    # Data actions
    EXPORT = "export"
    IMPORT = "import"
    SYNC = "sync"

    # Access actions
    VIEW = "view"
    DOWNLOAD = "download"
    PRINT = "print"

    # Admin actions
    INVITE = "invite"
    REVOKE = "revoke"
    DEACTIVATE = "deactivate"
    ACTIVATE = "activate"

    # Emergency/break-glass access
    EMERGENCY_ACCESS = "emergency_access"
    BREAK_GLASS = "break_glass"

    # Session events
    SESSION_REFRESH = "session_refresh"
    SESSION_REVOKE = "session_revoke"

    # Compliance
    VERIFY = "verify"
    BACKFILL = "backfill"
    INTEGRITY_CHECK_FAILED = "integrity_check_failed"


# PHI field categories for audit tracking
class PHICategory:
    """Categories of PHI fields for audit tracking."""

    DEMOGRAPHICS = ["first_name", "last_name", "date_of_birth", "gender", "address"]
    CONTACT = ["email", "phone"]
    CLINICAL = ["primary_diagnosis", "surgery_date", "medical_history"]
    VITALS = ["heart_rate", "blood_pressure", "spo2", "temperature"]
    IDENTIFIERS = ["mrn", "ssn", "insurance_id"]
