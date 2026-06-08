"""Build Cedar entities from SQLAlchemy models.

Cedar requires entities to be serialized in a specific format for evaluation.
This module transforms domain models into Cedar entity representations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from sense_loop.models import Organization, Patient, Practitioner


@dataclass
class CedarEntity:
    """Representation of a Cedar entity."""

    uid: str  # Format: "Type::\"id\""
    attrs: dict[str, Any]
    parents: list[str]  # List of parent UIDs

    def to_dict(self) -> dict[str, Any]:
        """Convert to Cedar JSON format."""
        return {
            "uid": self.uid,
            "attrs": self.attrs,
            "parents": [{"__expr": p} for p in self.parents] if self.parents else [],
        }


def make_entity_uid(entity_type: str, entity_id: str | UUID) -> str:
    """Create a Cedar entity UID string.

    Format: EntityType::"entity_id"
    """
    return f'{entity_type}::"{entity_id}"'


def build_practitioner_entity(
    practitioner: "Practitioner",
    organization_id: UUID,
    role_codes: list[str] | None = None,
) -> CedarEntity:
    """Build a Cedar entity for a practitioner.

    Args:
        practitioner: The practitioner model
        organization_id: The organization context
        role_codes: Optional list of role codes the practitioner has

    Returns:
        CedarEntity representing the practitioner
    """
    # Find the role for this organization
    org_role = None
    if hasattr(practitioner, "practitioner_roles"):
        for role in practitioner.practitioner_roles:
            if role.organization_id == organization_id and role.is_active:
                org_role = role
                break

    # Build parents (roles)
    parents = []
    if role_codes:
        for code in role_codes:
            parents.append(make_entity_uid("Role", code))
    elif org_role and org_role.role_definition:
        parents.append(make_entity_uid("Role", org_role.role_definition.code))

    # Build attributes
    attrs = {
        "email": practitioner.email,
        "is_active": practitioner.is_active,
        "organization_id": str(organization_id),
    }

    # Add role-based permissions if available
    if org_role and org_role.role_definition:
        rd = org_role.role_definition
        attrs["can_manage_patients"] = rd.can_manage_patients
        attrs["can_manage_alerts"] = rd.can_manage_alerts
        attrs["can_resolve_alerts"] = rd.can_resolve_alerts
        attrs["can_acknowledge_alerts"] = rd.can_acknowledge_alerts
        attrs["can_manage_care_plans"] = rd.can_manage_care_plans
        attrs["can_manage_clinicians"] = rd.can_manage_clinicians
        attrs["can_manage_org_settings"] = rd.can_manage_org_settings
        attrs["can_view_audit_logs"] = rd.can_view_audit_logs
        attrs["can_manage_alert_protocols"] = rd.can_manage_alert_protocols
        attrs["can_export_data"] = rd.can_export_data
        attrs["role_code"] = rd.code

    return CedarEntity(
        uid=make_entity_uid("Practitioner", str(practitioner.id)),
        attrs=attrs,
        parents=parents,
    )


def build_patient_entity(patient: "Patient") -> CedarEntity:
    """Build a Cedar entity for a patient.

    Args:
        patient: The patient model

    Returns:
        CedarEntity representing the patient
    """
    attrs = {
        "organization_id": str(patient.organization_id),
        "enrollment_status": patient.enrollment_status,
        "is_active": patient.is_active,
        "has_mrn": patient.mrn is not None,
    }

    # Add optional monitoring info
    if patient.monitoring_start_date:
        attrs["monitoring_start_date"] = patient.monitoring_start_date.isoformat()
    if patient.monitoring_end_date:
        attrs["monitoring_end_date"] = patient.monitoring_end_date.isoformat()
    if patient.surgery_date:
        attrs["surgery_date"] = patient.surgery_date.isoformat()

    return CedarEntity(
        uid=make_entity_uid("Patient", str(patient.id)),
        attrs=attrs,
        parents=[make_entity_uid("Organization", str(patient.organization_id))],
    )


def build_organization_entity(organization: "Organization") -> CedarEntity:
    """Build a Cedar entity for an organization.

    Args:
        organization: The organization model

    Returns:
        CedarEntity representing the organization
    """
    attrs = {
        "name": organization.name,
        "slug": organization.slug,
        "is_active": organization.is_active,
    }

    return CedarEntity(
        uid=make_entity_uid("Organization", str(organization.id)),
        attrs=attrs,
        parents=[],
    )


def build_resource_entity(
    resource_type: str,
    resource_id: UUID | None,
    organization_id: UUID,
    extra_attrs: dict[str, Any] | None = None,
) -> CedarEntity:
    """Build a generic Cedar entity for a resource.

    Args:
        resource_type: The type of resource (e.g., "Alert", "CarePlan")
        resource_id: The resource ID (can be None for type-level checks)
        organization_id: The organization the resource belongs to
        extra_attrs: Additional attributes for the entity

    Returns:
        CedarEntity representing the resource
    """
    attrs = {
        "organization_id": str(organization_id),
    }
    if extra_attrs:
        attrs.update(extra_attrs)

    # Use a placeholder ID for type-level checks
    entity_id = str(resource_id) if resource_id else "__type_check__"

    return CedarEntity(
        uid=make_entity_uid(resource_type.title(), entity_id),
        attrs=attrs,
        parents=[make_entity_uid("Organization", str(organization_id))],
    )


def build_action_entity(action: str) -> CedarEntity:
    """Build a Cedar entity for an action.

    Args:
        action: The action name (e.g., "read", "update", "delete")

    Returns:
        CedarEntity representing the action
    """
    return CedarEntity(
        uid=make_entity_uid("Action", action),
        attrs={"name": action},
        parents=[],
    )


def build_entities_for_authorization(
    practitioner: "Practitioner",
    resource_type: str,
    resource_id: UUID | None,
    organization_id: UUID,
    resource_attrs: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build all entities needed for an authorization check.

    Args:
        practitioner: The practitioner requesting access
        resource_type: The type of resource being accessed
        resource_id: The specific resource ID (or None for type-level)
        organization_id: The organization context
        resource_attrs: Additional attributes for the resource

    Returns:
        List of Cedar entity dictionaries ready for evaluation
    """
    entities = []

    # Build practitioner entity
    practitioner_entity = build_practitioner_entity(practitioner, organization_id)
    entities.append(practitioner_entity.to_dict())

    # Build resource entity
    resource_entity = build_resource_entity(
        resource_type, resource_id, organization_id, resource_attrs
    )
    entities.append(resource_entity.to_dict())

    # Build organization entity (as parent)
    org_entity = CedarEntity(
        uid=make_entity_uid("Organization", str(organization_id)),
        attrs={"id": str(organization_id)},
        parents=[],
    )
    entities.append(org_entity.to_dict())

    return entities
