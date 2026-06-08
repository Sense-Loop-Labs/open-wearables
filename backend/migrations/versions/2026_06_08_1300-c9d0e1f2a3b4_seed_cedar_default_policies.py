"""seed_cedar_default_policies

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3

"""

import json
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Default policies matching current permission flags
DEFAULT_POLICIES = [
    {
        "code": "patient_full_access",
        "name": "Patient Full Access",
        "description": "Full read/write access to patient records within the organization",
        "rules": {
            "resource_type": "patient",
            "actions": ["read", "create", "update", "delete"],
            "hidden_fields": ["password_hash"],
            "readonly_fields": [],
            "conditions": {"same_organization": True},
        },
        "effect": "permit",
        "priority": 100,
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
            "conditions": {"same_organization": True},
        },
        "effect": "permit",
        "priority": 50,
    },
    {
        "code": "alert_full_access",
        "name": "Alert Full Access",
        "description": "Full access to manage, acknowledge, and resolve alerts",
        "rules": {
            "resource_type": "alert",
            "actions": ["read", "create", "update", "acknowledge", "resolve"],
            "hidden_fields": [],
            "readonly_fields": [],
            "conditions": {"same_organization": True},
        },
        "effect": "permit",
        "priority": 100,
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
            "conditions": {"same_organization": True},
        },
        "effect": "permit",
        "priority": 50,
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
            "conditions": {"same_organization": True},
        },
        "effect": "permit",
        "priority": 75,
    },
    {
        "code": "care_plan_full_access",
        "name": "Care Plan Full Access",
        "description": "Full read/write access to care plans",
        "rules": {
            "resource_type": "care_plan",
            "actions": ["read", "create", "update", "delete"],
            "hidden_fields": [],
            "readonly_fields": [],
            "conditions": {"same_organization": True},
        },
        "effect": "permit",
        "priority": 100,
    },
    {
        "code": "clinician_management",
        "name": "Clinician Management",
        "description": "Can invite, update, and deactivate clinicians",
        "rules": {
            "resource_type": "practitioner",
            "actions": ["read", "create", "update", "delete", "invite"],
            "hidden_fields": ["password_hash", "password_reset_token"],
            "readonly_fields": [],
            "conditions": {"same_organization": True},
        },
        "effect": "permit",
        "priority": 100,
    },
    {
        "code": "org_settings_management",
        "name": "Organization Settings Management",
        "description": "Can update organization settings",
        "rules": {
            "resource_type": "organization",
            "actions": ["read", "update"],
            "hidden_fields": [],
            "readonly_fields": ["id", "created_at"],
            "conditions": {"same_organization": True},
        },
        "effect": "permit",
        "priority": 100,
    },
    {
        "code": "audit_log_access",
        "name": "Audit Log Access",
        "description": "Can view audit logs for compliance",
        "rules": {
            "resource_type": "audit_log",
            "actions": ["read"],
            "hidden_fields": [],
            "readonly_fields": [],
            "conditions": {"same_organization": True},
        },
        "effect": "permit",
        "priority": 100,
    },
    {
        "code": "alert_protocol_management",
        "name": "Alert Protocol Management",
        "description": "Can create and update alert protocols",
        "rules": {
            "resource_type": "alert_protocol",
            "actions": ["read", "create", "update", "delete"],
            "hidden_fields": [],
            "readonly_fields": [],
            "conditions": {"same_organization": True},
        },
        "effect": "permit",
        "priority": 100,
    },
    {
        "code": "data_export",
        "name": "Data Export Access",
        "description": "Can export patient and clinical data",
        "rules": {
            "resource_type": "patient",
            "actions": ["export"],
            "hidden_fields": [],
            "readonly_fields": [],
            "conditions": {"same_organization": True},
        },
        "effect": "permit",
        "priority": 100,
    },
    {
        "code": "communication_read_only",
        "name": "Communication Read Only",
        "description": "Can read but not send communications",
        "rules": {
            "resource_type": "communication",
            "actions": ["read"],
            "hidden_fields": [],
            "readonly_fields": [],
            "conditions": {"same_organization": True},
        },
        "effect": "permit",
        "priority": 50,
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
            "conditions": {"same_organization": True},
        },
        "effect": "permit",
        "priority": 100,
    },
]

# Mapping of role codes to their default policies
ROLE_POLICY_MAPPING = {
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


def upgrade() -> None:
    connection = op.get_bind()

    # Create policy ID lookup
    policy_ids = {}

    # Insert default policies
    for policy in DEFAULT_POLICIES:
        policy_id = str(uuid4())
        policy_ids[policy["code"]] = policy_id

        connection.execute(
            sa.text("""
                INSERT INTO sl_access_policy (id, code, name, description, organization_id, rules, effect, priority, is_active, is_system_policy)
                VALUES (:id, :code, :name, :description, NULL, CAST(:rules AS jsonb), :effect, :priority, true, true)
            """),
            {
                "id": policy_id,
                "code": policy["code"],
                "name": policy["name"],
                "description": policy["description"],
                "rules": json.dumps(policy["rules"]),
                "effect": policy["effect"],
                "priority": policy["priority"],
            },
        )

    # Get all system role definitions
    result = connection.execute(
        sa.text("SELECT id, code FROM sl_role_definition WHERE is_system_role = true")
    )
    role_definitions = {row[1]: row[0] for row in result}

    # Link policies to roles
    for role_code, policy_codes in ROLE_POLICY_MAPPING.items():
        role_id = role_definitions.get(role_code)
        if not role_id:
            continue

        for policy_code in policy_codes:
            policy_id = policy_ids.get(policy_code)
            if not policy_id:
                continue

            connection.execute(
                sa.text("""
                    INSERT INTO sl_role_access_policy (id, role_definition_id, access_policy_id, priority_override, is_active)
                    VALUES (:id, :role_definition_id, :access_policy_id, NULL, true)
                """),
                {
                    "id": str(uuid4()),
                    "role_definition_id": str(role_id),
                    "access_policy_id": policy_id,
                },
            )


def downgrade() -> None:
    connection = op.get_bind()

    # Delete role-policy links for system policies
    connection.execute(
        sa.text("""
            DELETE FROM sl_role_access_policy
            WHERE access_policy_id IN (
                SELECT id FROM sl_access_policy WHERE is_system_policy = true
            )
        """)
    )

    # Delete system policies
    connection.execute(
        sa.text("DELETE FROM sl_access_policy WHERE is_system_policy = true")
    )
