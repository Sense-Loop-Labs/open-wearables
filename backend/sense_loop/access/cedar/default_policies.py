"""Default Cedar policies matching current permission flags.

These policies provide the same authorization as the current 10 boolean
permission flags, allowing for backward compatibility during transition.
"""

from typing import Any

# Default policies that mirror the current permission system
DEFAULT_POLICIES: list[dict[str, Any]] = [
    # Patient management policies
    {
        "code": "patient_full_access",
        "name": "Patient Full Access",
        "description": "Full read/write access to patient records within the organization",
        "rules": {
            "resource_type": "patient",
            "actions": ["read", "create", "update", "delete"],
            "hidden_fields": ["password_hash"],
            "readonly_fields": [],
            "conditions": {
                "same_organization": True,
            },
        },
        "effect": "permit",
        "priority": 100,
        "is_system_policy": True,
    },
    {
        "code": "patient_read_only",
        "name": "Patient Read Only",
        "description": "Read-only access to patient records within the organization",
        "rules": {
            "resource_type": "patient",
            "actions": ["read"],
            "hidden_fields": ["password_hash", "activation_code"],
            "readonly_fields": [],
            "conditions": {
                "same_organization": True,
            },
        },
        "effect": "permit",
        "priority": 50,
        "is_system_policy": True,
    },
    # Alert management policies
    {
        "code": "alert_full_access",
        "name": "Alert Full Access",
        "description": "Full access to manage, acknowledge, and resolve alerts",
        "rules": {
            "resource_type": "alert",
            "actions": ["read", "create", "update", "acknowledge", "resolve"],
            "hidden_fields": [],
            "readonly_fields": [],
            "conditions": {
                "same_organization": True,
            },
        },
        "effect": "permit",
        "priority": 100,
        "is_system_policy": True,
    },
    {
        "code": "alert_acknowledge_only",
        "name": "Alert Acknowledge Only",
        "description": "Can read and acknowledge alerts but not resolve them",
        "rules": {
            "resource_type": "alert",
            "actions": ["read", "acknowledge"],
            "hidden_fields": [],
            "readonly_fields": [],
            "conditions": {
                "same_organization": True,
            },
        },
        "effect": "permit",
        "priority": 50,
        "is_system_policy": True,
    },
    {
        "code": "alert_resolve",
        "name": "Alert Resolve Access",
        "description": "Can resolve alerts (in addition to acknowledge)",
        "rules": {
            "resource_type": "alert",
            "actions": ["resolve"],
            "hidden_fields": [],
            "readonly_fields": [],
            "conditions": {
                "same_organization": True,
            },
        },
        "effect": "permit",
        "priority": 75,
        "is_system_policy": True,
    },
    # Care plan management policies
    {
        "code": "care_plan_full_access",
        "name": "Care Plan Full Access",
        "description": "Full read/write access to care plans",
        "rules": {
            "resource_type": "care_plan",
            "actions": ["read", "create", "update", "delete"],
            "hidden_fields": [],
            "readonly_fields": [],
            "conditions": {
                "same_organization": True,
            },
        },
        "effect": "permit",
        "priority": 100,
        "is_system_policy": True,
    },
    # Clinician management policies
    {
        "code": "clinician_management",
        "name": "Clinician Management",
        "description": "Can invite, update, and deactivate clinicians",
        "rules": {
            "resource_type": "practitioner",
            "actions": ["read", "create", "update", "delete", "invite"],
            "hidden_fields": ["password_hash", "password_reset_token"],
            "readonly_fields": [],
            "conditions": {
                "same_organization": True,
            },
        },
        "effect": "permit",
        "priority": 100,
        "is_system_policy": True,
    },
    # Organization settings policies
    {
        "code": "org_settings_management",
        "name": "Organization Settings Management",
        "description": "Can update organization settings",
        "rules": {
            "resource_type": "organization",
            "actions": ["read", "update"],
            "hidden_fields": [],
            "readonly_fields": ["id", "created_at"],
            "conditions": {
                "same_organization": True,
            },
        },
        "effect": "permit",
        "priority": 100,
        "is_system_policy": True,
    },
    # Audit log policies
    {
        "code": "audit_log_access",
        "name": "Audit Log Access",
        "description": "Can view audit logs for compliance",
        "rules": {
            "resource_type": "audit_log",
            "actions": ["read"],
            "hidden_fields": [],
            "readonly_fields": [],
            "conditions": {
                "same_organization": True,
            },
        },
        "effect": "permit",
        "priority": 100,
        "is_system_policy": True,
    },
    # Alert protocol policies
    {
        "code": "alert_protocol_management",
        "name": "Alert Protocol Management",
        "description": "Can create and update alert protocols",
        "rules": {
            "resource_type": "alert_protocol",
            "actions": ["read", "create", "update", "delete"],
            "hidden_fields": [],
            "readonly_fields": [],
            "conditions": {
                "same_organization": True,
            },
        },
        "effect": "permit",
        "priority": 100,
        "is_system_policy": True,
    },
    # Data export policies
    {
        "code": "data_export",
        "name": "Data Export Access",
        "description": "Can export patient and clinical data",
        "rules": {
            "resource_type": "patient",
            "actions": ["export"],
            "hidden_fields": [],
            "readonly_fields": [],
            "conditions": {
                "same_organization": True,
            },
        },
        "effect": "permit",
        "priority": 100,
        "is_system_policy": True,
    },
    # Communication/messaging policies (for the MA override example)
    {
        "code": "communication_read_only",
        "name": "Communication Read Only",
        "description": "Can read but not send communications",
        "rules": {
            "resource_type": "communication",
            "actions": ["read"],
            "hidden_fields": [],
            "readonly_fields": [],
            "conditions": {
                "same_organization": True,
            },
        },
        "effect": "permit",
        "priority": 50,
        "is_system_policy": True,
    },
    {
        "code": "communication_full_access",
        "name": "Communication Full Access",
        "description": "Can read, create, and send communications",
        "rules": {
            "resource_type": "communication",
            "actions": ["read", "create", "send"],
            "hidden_fields": [],
            "readonly_fields": [],
            "conditions": {
                "same_organization": True,
            },
        },
        "effect": "permit",
        "priority": 100,
        "is_system_policy": True,
    },
]

# Mapping of role codes to their default policies
# Based on the current permission flags in RoleDefinition
ROLE_POLICY_MAPPING: dict[str, list[str]] = {
    "super_admin": [
        "patient_full_access",
        "alert_full_access",
        "care_plan_full_access",
        "clinician_management",
        "org_settings_management",
        "audit_log_access",
        "alert_protocol_management",
        "data_export",
        "communication_full_access",
    ],
    "org_admin": [
        "patient_full_access",
        "alert_full_access",
        "care_plan_full_access",
        "clinician_management",
        "org_settings_management",
        "audit_log_access",
        "data_export",
        "communication_full_access",
    ],
    "doctor": [
        "patient_full_access",
        "alert_full_access",
        "care_plan_full_access",
        "data_export",
        "communication_full_access",
    ],
    "physician_assistant": [
        "patient_full_access",
        "alert_full_access",
        "care_plan_full_access",
        "data_export",
        "communication_full_access",
    ],
    "nurse_practitioner": [
        "patient_full_access",
        "alert_full_access",
        "care_plan_full_access",
        "data_export",
        "communication_full_access",
    ],
    "nurse": [
        "patient_full_access",
        "alert_acknowledge_only",
        "care_plan_full_access",
        "communication_full_access",
    ],
    "medical_assistant": [
        "patient_full_access",
        "alert_acknowledge_only",
        "communication_read_only",
    ],
    "care_coordinator": [
        "patient_full_access",
        "alert_acknowledge_only",
        "care_plan_full_access",
        "communication_read_only",
    ],
    "readonly": [
        "patient_read_only",
    ],
}


def get_policy_by_code(code: str) -> dict[str, Any] | None:
    """Get a default policy by its code.

    Args:
        code: The policy code

    Returns:
        Policy definition dict or None if not found
    """
    for policy in DEFAULT_POLICIES:
        if policy["code"] == code:
            return policy
    return None


def get_policies_for_role(role_code: str) -> list[dict[str, Any]]:
    """Get default policies for a role.

    Args:
        role_code: The role code (e.g., 'doctor', 'nurse')

    Returns:
        List of policy definitions for the role
    """
    policy_codes = ROLE_POLICY_MAPPING.get(role_code, [])
    return [p for p in DEFAULT_POLICIES if p["code"] in policy_codes]
