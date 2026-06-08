"""Cedar-based authorization database models.

These models store flexible access policies that can be evaluated using Cedar
policy language, providing fine-grained field-level access control.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_50, str_100, str_255


class AccessPolicy(BaseDbModel):
    """Flexible access policy definition.

    Policies define what actions are permitted on resources, including
    field-level controls for hidden and readonly fields.

    Rules schema:
    {
        "resource_type": "patient",
        "actions": ["read", "update"],
        "hidden_fields": ["ssn", "password_hash"],
        "readonly_fields": ["mrn", "date_of_birth"],
        "conditions": {
            "same_organization": true,
            "enrollment_status": ["active"]
        }
    }
    """

    __tablename__ = "sl_access_policy"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_access_policy_org_code"),
    )

    id: Mapped[PrimaryKey[UUID]]

    # Unique identifier for programmatic reference
    code: Mapped[str_100]  # e.g., "nurse_patient_read", "ma_exception_send_messages"

    # Human-readable name and description
    name: Mapped[str_255]
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Organization scope: None = system-wide policy
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_organization.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Policy rules (JSONB for flexibility)
    rules: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Effect: "permit" or "forbid"
    effect: Mapped[str_50] = mapped_column(default="permit")

    # Priority: higher values evaluated first (for conflict resolution)
    priority: Mapped[int] = mapped_column(default=0)

    # Status flags
    is_active: Mapped[bool] = mapped_column(default=True)
    is_system_policy: Mapped[bool] = mapped_column(default=False)

    # Relationships
    organization: Mapped["Organization | None"] = relationship(
        foreign_keys=[organization_id],
    )
    role_policies: Mapped[list["RoleAccessPolicy"]] = relationship(
        back_populates="access_policy",
        cascade="all, delete-orphan",
    )
    practitioner_policies: Mapped[list["PractitionerAccessPolicy"]] = relationship(
        back_populates="access_policy",
        cascade="all, delete-orphan",
    )


class RoleAccessPolicy(BaseDbModel):
    """Links AccessPolicy to RoleDefinition.

    Provides role-based policy assignment, allowing all practitioners
    with a given role to inherit the associated policies.
    """

    __tablename__ = "sl_role_access_policy"
    __table_args__ = (
        UniqueConstraint(
            "role_definition_id", "access_policy_id", name="uq_role_access_policy"
        ),
    )

    id: Mapped[PrimaryKey[UUID]]

    # Foreign keys
    role_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_role_definition.id", ondelete="CASCADE"),
        index=True,
    )
    access_policy_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_access_policy.id", ondelete="CASCADE"),
        index=True,
    )

    # Optional priority override (if set, overrides the policy's default priority)
    priority_override: Mapped[int | None] = mapped_column(nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    role_definition: Mapped["RoleDefinition"] = relationship(
        foreign_keys=[role_definition_id],
    )
    access_policy: Mapped["AccessPolicy"] = relationship(
        back_populates="role_policies",
    )

    @property
    def effective_priority(self) -> int:
        """Get the effective priority (override or policy default)."""
        if self.priority_override is not None:
            return self.priority_override
        return self.access_policy.priority


class PractitionerAccessPolicy(BaseDbModel):
    """Individual practitioner policy overrides.

    Allows granting specific policies to individual practitioners,
    with optional time bounds for temporary access.
    """

    __tablename__ = "sl_practitioner_access_policy"
    __table_args__ = (
        UniqueConstraint(
            "practitioner_id",
            "organization_id",
            "access_policy_id",
            name="uq_practitioner_access_policy",
        ),
    )

    id: Mapped[PrimaryKey[UUID]]

    # Foreign keys
    practitioner_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_practitioner.id", ondelete="CASCADE"),
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_organization.id", ondelete="CASCADE"),
        index=True,
    )
    access_policy_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_access_policy.id", ondelete="CASCADE"),
        index=True,
    )

    # Time bounds for temporary access
    valid_from: Mapped[datetime | None] = mapped_column(nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(nullable=True)

    # Audit trail
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    granted_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_practitioner.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    practitioner: Mapped["Practitioner"] = relationship(
        foreign_keys=[practitioner_id],
    )
    organization: Mapped["Organization"] = relationship(
        foreign_keys=[organization_id],
    )
    access_policy: Mapped["AccessPolicy"] = relationship(
        back_populates="practitioner_policies",
    )
    granted_by: Mapped["Practitioner | None"] = relationship(
        foreign_keys=[granted_by_id],
    )

    def is_valid(self, at_time: datetime | None = None) -> bool:
        """Check if this policy assignment is currently valid."""
        if at_time is None:
            at_time = datetime.now()

        if self.valid_from and at_time < self.valid_from:
            return False
        if self.valid_until and at_time > self.valid_until:
            return False
        return True


class BreakTheGlassAccess(BaseDbModel):
    """Emergency access records for break-the-glass scenarios.

    Provides time-limited emergency access with full audit trail
    for HIPAA compliance.
    """

    __tablename__ = "sl_break_glass_access"

    id: Mapped[PrimaryKey[UUID]]

    # Who is accessing
    practitioner_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_practitioner.id", ondelete="CASCADE"),
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_organization.id", ondelete="CASCADE"),
        index=True,
    )

    # What resource type and optionally specific resource
    resource_type: Mapped[str_50]
    resource_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)

    # Required justification
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # Emergency type classification
    emergency_type: Mapped[str_50]  # e.g., "medical_emergency", "system_outage", "disaster_recovery"

    # Time bounds
    activated_at: Mapped[datetime] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Revocation info
    revoked_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_practitioner.id", ondelete="SET NULL"),
        nullable=True,
    )
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Access tracking
    access_count: Mapped[int] = mapped_column(default=0)
    last_access_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    practitioner: Mapped["Practitioner"] = relationship(
        foreign_keys=[practitioner_id],
    )
    organization: Mapped["Organization"] = relationship(
        foreign_keys=[organization_id],
    )
    revoked_by: Mapped["Practitioner | None"] = relationship(
        foreign_keys=[revoked_by_id],
    )

    def is_active(self, at_time: datetime | None = None) -> bool:
        """Check if this BTG access is currently active."""
        if at_time is None:
            at_time = datetime.now()

        if self.revoked_at:
            return False
        if at_time < self.activated_at:
            return False
        if at_time > self.expires_at:
            return False
        return True

    def increment_access(self) -> None:
        """Record an access under this BTG grant."""
        self.access_count += 1
        self.last_access_at = datetime.now()
