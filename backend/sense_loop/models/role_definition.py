"""Role definition model for flexible RBAC."""

from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_50, str_100


class RoleDefinition(BaseDbModel):
    """Flexible role definitions with permission flags.

    Roles can be system-wide (organization_id is None) or org-specific.
    Organizations can create custom roles with specific permission combinations.
    """

    __tablename__ = "sl_role_definition"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_role_org_code"),
    )

    id: Mapped[PrimaryKey[UUID]]

    # None = system-wide role, otherwise org-specific
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_organization.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    code: Mapped[str_50]  # 'doctor', 'nurse', 'org_admin', etc.
    display_name: Mapped[str_100]  # 'Physician', 'Nurse', 'Organization Admin'

    # Permission flags
    can_manage_patients: Mapped[bool] = mapped_column(default=True)
    can_manage_alerts: Mapped[bool] = mapped_column(default=True)
    can_resolve_alerts: Mapped[bool] = mapped_column(default=True)
    can_acknowledge_alerts: Mapped[bool] = mapped_column(default=True)
    can_manage_care_plans: Mapped[bool] = mapped_column(default=True)
    can_manage_clinicians: Mapped[bool] = mapped_column(default=False)
    can_manage_org_settings: Mapped[bool] = mapped_column(default=False)
    can_view_audit_logs: Mapped[bool] = mapped_column(default=False)
    can_manage_alert_protocols: Mapped[bool] = mapped_column(default=False)
    can_export_data: Mapped[bool] = mapped_column(default=False)

    # Meta
    is_system_role: Mapped[bool] = mapped_column(default=False)  # True for built-in roles
    is_active: Mapped[bool] = mapped_column(default=True)

    # Privilege level for role assignment hierarchy
    # Higher level = more privileged. Users can only assign roles at or below their level.
    # e.g., org_admin (80) can assign doctor (60) but not another org_admin
    privilege_level: Mapped[int] = mapped_column(default=50)

    # Relationships
    organization: Mapped["Organization | None"] = relationship(
        back_populates="role_definitions",
        foreign_keys=[organization_id],
    )
    practitioner_roles: Mapped[list["PractitionerRole"]] = relationship(
        back_populates="role_definition",
    )


# Default system roles to seed
# privilege_level: Higher = more privileged. Users can only assign roles at or below their level.
DEFAULT_ROLES = [
    {
        "code": "super_admin",
        "display_name": "Super Admin",
        "privilege_level": 100,
        "can_manage_patients": True,
        "can_manage_alerts": True,
        "can_resolve_alerts": True,
        "can_acknowledge_alerts": True,
        "can_manage_care_plans": True,
        "can_manage_clinicians": True,
        "can_manage_org_settings": True,
        "can_view_audit_logs": True,
        "can_manage_alert_protocols": True,
        "can_export_data": True,
        "is_system_role": True,
    },
    {
        "code": "org_admin",
        "display_name": "Organization Admin",
        "privilege_level": 80,
        "can_manage_patients": True,
        "can_manage_alerts": True,
        "can_resolve_alerts": True,
        "can_acknowledge_alerts": True,
        "can_manage_care_plans": True,
        "can_manage_clinicians": True,
        "can_manage_org_settings": True,
        "can_view_audit_logs": True,
        "can_manage_alert_protocols": False,
        "can_export_data": True,
        "is_system_role": True,
    },
    {
        "code": "doctor",
        "display_name": "Physician",
        "privilege_level": 60,
        "can_manage_patients": True,
        "can_manage_alerts": True,
        "can_resolve_alerts": True,
        "can_acknowledge_alerts": True,
        "can_manage_care_plans": True,
        "can_manage_clinicians": False,
        "can_manage_org_settings": False,
        "can_view_audit_logs": False,
        "can_manage_alert_protocols": False,
        "can_export_data": True,
        "is_system_role": True,
    },
    {
        "code": "physician_assistant",
        "display_name": "Physician Assistant",
        "privilege_level": 55,
        "can_manage_patients": True,
        "can_manage_alerts": True,
        "can_resolve_alerts": True,
        "can_acknowledge_alerts": True,
        "can_manage_care_plans": True,
        "can_manage_clinicians": False,
        "can_manage_org_settings": False,
        "can_view_audit_logs": False,
        "can_manage_alert_protocols": False,
        "can_export_data": True,
        "is_system_role": True,
    },
    {
        "code": "nurse_practitioner",
        "display_name": "Nurse Practitioner",
        "privilege_level": 55,
        "can_manage_patients": True,
        "can_manage_alerts": True,
        "can_resolve_alerts": True,
        "can_acknowledge_alerts": True,
        "can_manage_care_plans": True,
        "can_manage_clinicians": False,
        "can_manage_org_settings": False,
        "can_view_audit_logs": False,
        "can_manage_alert_protocols": False,
        "can_export_data": True,
        "is_system_role": True,
    },
    {
        "code": "nurse",
        "display_name": "Nurse",
        "privilege_level": 50,
        "can_manage_patients": True,
        "can_manage_alerts": True,
        "can_resolve_alerts": False,
        "can_acknowledge_alerts": True,
        "can_manage_care_plans": True,
        "can_manage_clinicians": False,
        "can_manage_org_settings": False,
        "can_view_audit_logs": False,
        "can_manage_alert_protocols": False,
        "can_export_data": False,
        "is_system_role": True,
    },
    {
        "code": "medical_assistant",
        "display_name": "Medical Assistant",
        "privilege_level": 40,
        "can_manage_patients": True,
        "can_manage_alerts": False,
        "can_resolve_alerts": False,
        "can_acknowledge_alerts": True,
        "can_manage_care_plans": False,
        "can_manage_clinicians": False,
        "can_manage_org_settings": False,
        "can_view_audit_logs": False,
        "can_manage_alert_protocols": False,
        "can_export_data": False,
        "is_system_role": True,
    },
    {
        "code": "care_coordinator",
        "display_name": "Care Coordinator",
        "privilege_level": 45,
        "can_manage_patients": True,
        "can_manage_alerts": False,
        "can_resolve_alerts": False,
        "can_acknowledge_alerts": True,
        "can_manage_care_plans": True,
        "can_manage_clinicians": False,
        "can_manage_org_settings": False,
        "can_view_audit_logs": False,
        "can_manage_alert_protocols": False,
        "can_export_data": False,
        "is_system_role": True,
    },
    {
        "code": "readonly",
        "display_name": "Read Only",
        "privilege_level": 10,
        "can_manage_patients": False,
        "can_manage_alerts": False,
        "can_resolve_alerts": False,
        "can_acknowledge_alerts": False,
        "can_manage_care_plans": False,
        "can_manage_clinicians": False,
        "can_manage_org_settings": False,
        "can_view_audit_logs": False,
        "can_manage_alert_protocols": False,
        "can_export_data": False,
        "is_system_role": True,
    },
]
