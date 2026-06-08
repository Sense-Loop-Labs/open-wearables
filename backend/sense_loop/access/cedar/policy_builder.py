"""Generate Cedar policy DSL from database records.

This module transforms AccessPolicy database records into Cedar
policy language that can be evaluated by the Cedar engine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import AccessPolicy


def build_cedar_policy(policy: "AccessPolicy") -> str:
    """Build a Cedar policy string from an AccessPolicy record.

    Args:
        policy: The AccessPolicy database record

    Returns:
        Cedar policy string in Cedar DSL format
    """
    rules = policy.rules
    effect = policy.effect.lower()

    # Extract policy components
    resource_type = rules.get("resource_type", "Resource")
    actions = rules.get("actions", [])
    conditions = rules.get("conditions", {})

    # Normalize resource type for Cedar (PascalCase)
    cedar_resource = resource_type.title().replace("_", "")

    # Build action list for Cedar
    if actions:
        action_list = ", ".join(
            f'Action::"{action}"' for action in actions
        )
        action_clause = f"action in [{action_list}]"
    else:
        action_clause = "action"  # Any action

    # Build condition clauses
    condition_clauses = _build_condition_clauses(conditions)

    # Build the policy
    policy_lines = [
        f"// Policy: {policy.code}",
        f"// Priority: {policy.priority}",
        f"{effect} (",
        f"  principal,",
        f"  {action_clause},",
        f"  resource is {cedar_resource}",
        ")",
    ]

    if condition_clauses:
        policy_lines.append("when {")
        for clause in condition_clauses:
            policy_lines.append(f"  {clause}")
        policy_lines.append("};")
    else:
        policy_lines.append(";")

    return "\n".join(policy_lines)


def _build_condition_clauses(conditions: dict[str, Any]) -> list[str]:
    """Build Cedar condition clauses from policy conditions.

    Args:
        conditions: Dictionary of condition specifications

    Returns:
        List of Cedar condition clause strings
    """
    clauses = []

    # Same organization check
    if conditions.get("same_organization"):
        clauses.append(
            "principal.organization_id == resource.organization_id"
        )

    # Enrollment status filter
    if "enrollment_status" in conditions:
        statuses = conditions["enrollment_status"]
        if isinstance(statuses, list) and statuses:
            status_checks = " || ".join(
                f'resource.enrollment_status == "{s}"' for s in statuses
            )
            clauses.append(f"({status_checks})")

    # Active resource check
    if conditions.get("resource_active"):
        clauses.append("resource.is_active == true")

    # Time-based conditions
    if "time_range" in conditions:
        time_range = conditions["time_range"]
        if "start" in time_range:
            clauses.append(f'context.current_time >= "{time_range["start"]}"')
        if "end" in time_range:
            clauses.append(f'context.current_time <= "{time_range["end"]}"')

    # Custom attribute conditions
    if "resource_attrs" in conditions:
        for attr, value in conditions["resource_attrs"].items():
            if isinstance(value, bool):
                clauses.append(f"resource.{attr} == {str(value).lower()}")
            elif isinstance(value, (int, float)):
                clauses.append(f"resource.{attr} == {value}")
            elif isinstance(value, str):
                clauses.append(f'resource.{attr} == "{value}"')
            elif isinstance(value, list):
                # IN check
                value_checks = " || ".join(
                    f'resource.{attr} == "{v}"' if isinstance(v, str) else f"resource.{attr} == {v}"
                    for v in value
                )
                clauses.append(f"({value_checks})")

    # Principal attribute conditions
    if "principal_attrs" in conditions:
        for attr, value in conditions["principal_attrs"].items():
            if isinstance(value, bool):
                clauses.append(f"principal.{attr} == {str(value).lower()}")
            elif isinstance(value, (int, float)):
                clauses.append(f"principal.{attr} == {value}")
            elif isinstance(value, str):
                clauses.append(f'principal.{attr} == "{value}"')

    return clauses


def build_cedar_schema() -> str:
    """Build the Cedar schema for Sense Loop entities.

    Returns:
        Cedar schema definition string
    """
    return """
namespace SenseLoop {
    entity Organization = {
        name: String,
        slug: String,
        is_active: Bool,
    };

    entity Role;

    entity Practitioner in [Role] = {
        email: String,
        is_active: Bool,
        organization_id: String,
        can_manage_patients: Bool,
        can_manage_alerts: Bool,
        can_resolve_alerts: Bool,
        can_acknowledge_alerts: Bool,
        can_manage_care_plans: Bool,
        can_manage_clinicians: Bool,
        can_manage_org_settings: Bool,
        can_view_audit_logs: Bool,
        can_manage_alert_protocols: Bool,
        can_export_data: Bool,
        role_code?: String,
    };

    entity Patient in [Organization] = {
        organization_id: String,
        enrollment_status: String,
        is_active: Bool,
        has_mrn: Bool,
        monitoring_start_date?: String,
        monitoring_end_date?: String,
        surgery_date?: String,
    };

    entity Alert in [Organization] = {
        organization_id: String,
        patient_id: String,
        severity: String,
        status: String,
        is_active: Bool,
    };

    entity CarePlan in [Organization] = {
        organization_id: String,
        patient_id: String,
        status: String,
        is_active: Bool,
    };

    entity Communication in [Organization] = {
        organization_id: String,
        patient_id?: String,
        message_type: String,
        is_active: Bool,
    };

    entity Resource in [Organization] = {
        organization_id: String,
        is_active: Bool,
    };

    action read appliesTo {
        principal: [Practitioner],
        resource: [Patient, Alert, CarePlan, Communication, Resource],
    };

    action create appliesTo {
        principal: [Practitioner],
        resource: [Patient, Alert, CarePlan, Communication, Resource],
    };

    action update appliesTo {
        principal: [Practitioner],
        resource: [Patient, Alert, CarePlan, Communication, Resource],
    };

    action delete appliesTo {
        principal: [Practitioner],
        resource: [Patient, Alert, CarePlan, Communication, Resource],
    };

    action acknowledge appliesTo {
        principal: [Practitioner],
        resource: [Alert],
    };

    action resolve appliesTo {
        principal: [Practitioner],
        resource: [Alert],
    };

    action send appliesTo {
        principal: [Practitioner],
        resource: [Communication],
    };

    action export appliesTo {
        principal: [Practitioner],
        resource: [Patient, Alert, CarePlan, Resource],
    };
}
"""


def build_policies_from_db(policies: list["AccessPolicy"]) -> str:
    """Build combined Cedar policies from a list of AccessPolicy records.

    Args:
        policies: List of AccessPolicy records

    Returns:
        Combined Cedar policy string
    """
    # Sort by priority (higher first)
    sorted_policies = sorted(policies, key=lambda p: -p.priority)

    policy_strings = []
    for policy in sorted_policies:
        if policy.is_active:
            policy_strings.append(build_cedar_policy(policy))

    return "\n\n".join(policy_strings)


def get_hidden_fields_from_policy(policy: "AccessPolicy") -> list[str]:
    """Extract hidden fields from a policy's rules.

    Args:
        policy: The AccessPolicy record

    Returns:
        List of field names that should be hidden
    """
    return policy.rules.get("hidden_fields", [])


def get_readonly_fields_from_policy(policy: "AccessPolicy") -> list[str]:
    """Extract readonly fields from a policy's rules.

    Args:
        policy: The AccessPolicy record

    Returns:
        List of field names that should be readonly
    """
    return policy.rules.get("readonly_fields", [])
