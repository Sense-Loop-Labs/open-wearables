"""Practitioner role model - links practitioner to organization with a role."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey


class PractitionerRole(BaseDbModel):
    """Links a practitioner to an organization with a specific role.

    A practitioner can have multiple roles across different organizations.
    """

    __tablename__ = "sl_practitioner_role"
    __table_args__ = (
        UniqueConstraint(
            "practitioner_id", "organization_id",
            name="uq_practitioner_org",
        ),
    )

    id: Mapped[PrimaryKey[UUID]]

    practitioner_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_practitioner.id", ondelete="CASCADE"),
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_organization.id", ondelete="CASCADE"),
        index=True,
    )
    role_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_role_definition.id", ondelete="RESTRICT"),
        index=True,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    is_primary: Mapped[bool] = mapped_column(default=False)  # Primary org for this practitioner

    # Timestamps
    invited_at: Mapped[datetime | None] = mapped_column(nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    practitioner: Mapped["Practitioner"] = relationship(
        back_populates="practitioner_roles",
    )
    organization: Mapped["Organization"] = relationship(
        back_populates="practitioner_roles",
    )
    role_definition: Mapped["RoleDefinition"] = relationship(
        back_populates="practitioner_roles",
    )

    @property
    def has_permission(self) -> dict[str, bool]:
        """Get permission flags from role definition."""
        rd = self.role_definition
        return {
            "can_manage_patients": rd.can_manage_patients,
            "can_manage_alerts": rd.can_manage_alerts,
            "can_resolve_alerts": rd.can_resolve_alerts,
            "can_acknowledge_alerts": rd.can_acknowledge_alerts,
            "can_manage_care_plans": rd.can_manage_care_plans,
            "can_manage_clinicians": rd.can_manage_clinicians,
            "can_manage_org_settings": rd.can_manage_org_settings,
            "can_view_audit_logs": rd.can_view_audit_logs,
            "can_manage_alert_protocols": rd.can_manage_alert_protocols,
            "can_export_data": rd.can_export_data,
        }
