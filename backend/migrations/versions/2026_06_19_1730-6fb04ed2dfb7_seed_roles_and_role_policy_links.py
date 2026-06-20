"""seed_roles_and_role_policy_links

This migration ensures roles and role-policy links are seeded during alembic upgrade.
Previously, roles were seeded via a script that ran AFTER migrations, causing the
access policy migration to fail to create role-policy links (since roles didn't exist yet).

This migration is idempotent - it only inserts missing data.

Revision ID: 6fb04ed2dfb7
Revises: a7e8f9a0b1c2
"""

from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6fb04ed2dfb7"
down_revision: Union[str, None] = "a7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Default system roles (same as role_definition.py DEFAULT_ROLES)
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


# Role-to-policy mappings (same as seed_sl_access_policies.py)
ROLE_POLICY_MAPPINGS = {
    "super_admin": [
        "alert_full_access",
        "alert_protocol_management",
        "audit_log_access",
        "care_plan_full_access",
        "clinician_management",
        "communication_full_access",
        "data_export",
        "org_settings_management",
        "patient_full_access",
    ],
    "org_admin": [
        "alert_full_access",
        "audit_log_access",
        "care_plan_full_access",
        "clinician_management",
        "communication_full_access",
        "data_export",
        "org_settings_management",
        "patient_full_access",
    ],
    "doctor": [
        "alert_full_access",
        "care_plan_full_access",
        "communication_full_access",
        "data_export",
        "patient_full_access",
    ],
    "physician_assistant": [
        "alert_full_access",
        "care_plan_full_access",
        "communication_full_access",
        "data_export",
        "patient_full_access",
    ],
    "nurse_practitioner": [
        "alert_full_access",
        "care_plan_full_access",
        "communication_full_access",
        "data_export",
        "patient_full_access",
    ],
    "nurse": [
        "alert_acknowledge_only",
        "care_plan_full_access",
        "communication_full_access",
        "patient_full_access",
    ],
    "medical_assistant": [
        "alert_acknowledge_only",
        "communication_read_only",
        "patient_full_access",
    ],
    "care_coordinator": [
        "alert_acknowledge_only",
        "care_plan_full_access",
        "communication_read_only",
        "patient_full_access",
    ],
    "readonly": [
        "patient_read_only",
    ],
}


def upgrade() -> None:
    connection = op.get_bind()

    # Step 1: Seed roles if they don't exist
    for role in DEFAULT_ROLES:
        # Check if role exists
        result = connection.execute(
            sa.text(
                "SELECT id FROM sl_role_definition WHERE code = :code AND organization_id IS NULL"
            ),
            {"code": role["code"]},
        )
        existing = result.fetchone()

        if existing:
            continue

        # Insert role
        role_id = str(uuid4())
        connection.execute(
            sa.text("""
                INSERT INTO sl_role_definition (
                    id, organization_id, code, display_name, privilege_level,
                    can_manage_patients, can_manage_alerts, can_resolve_alerts,
                    can_acknowledge_alerts, can_manage_care_plans, can_manage_clinicians,
                    can_manage_org_settings, can_view_audit_logs, can_manage_alert_protocols,
                    can_export_data, is_system_role, is_active
                ) VALUES (
                    :id, NULL, :code, :display_name, :privilege_level,
                    :can_manage_patients, :can_manage_alerts, :can_resolve_alerts,
                    :can_acknowledge_alerts, :can_manage_care_plans, :can_manage_clinicians,
                    :can_manage_org_settings, :can_view_audit_logs, :can_manage_alert_protocols,
                    :can_export_data, :is_system_role, true
                )
            """),
            {
                "id": role_id,
                "code": role["code"],
                "display_name": role["display_name"],
                "privilege_level": role["privilege_level"],
                "can_manage_patients": role["can_manage_patients"],
                "can_manage_alerts": role["can_manage_alerts"],
                "can_resolve_alerts": role["can_resolve_alerts"],
                "can_acknowledge_alerts": role["can_acknowledge_alerts"],
                "can_manage_care_plans": role["can_manage_care_plans"],
                "can_manage_clinicians": role["can_manage_clinicians"],
                "can_manage_org_settings": role["can_manage_org_settings"],
                "can_view_audit_logs": role["can_view_audit_logs"],
                "can_manage_alert_protocols": role["can_manage_alert_protocols"],
                "can_export_data": role["can_export_data"],
                "is_system_role": role["is_system_role"],
            },
        )

    # Step 2: Build lookup maps for roles and policies
    role_map = {}
    result = connection.execute(
        sa.text(
            "SELECT id, code FROM sl_role_definition WHERE is_system_role = true AND organization_id IS NULL"
        )
    )
    for row in result:
        role_map[row[1]] = row[0]

    policy_map = {}
    result = connection.execute(
        sa.text(
            "SELECT id, code FROM sl_access_policy WHERE is_system_policy = true"
        )
    )
    for row in result:
        policy_map[row[1]] = row[0]

    # Step 3: Seed role-policy links if they don't exist
    for role_code, policy_codes in ROLE_POLICY_MAPPINGS.items():
        role_id = role_map.get(role_code)
        if not role_id:
            continue

        for policy_code in policy_codes:
            policy_id = policy_map.get(policy_code)
            if not policy_id:
                continue

            # Check if link exists
            result = connection.execute(
                sa.text("""
                    SELECT id FROM sl_role_access_policy
                    WHERE role_definition_id = :role_id AND access_policy_id = :policy_id
                """),
                {"role_id": str(role_id), "policy_id": str(policy_id)},
            )
            if result.fetchone():
                continue

            # Insert link
            connection.execute(
                sa.text("""
                    INSERT INTO sl_role_access_policy (id, role_definition_id, access_policy_id, is_active)
                    VALUES (:id, :role_id, :policy_id, true)
                """),
                {
                    "id": str(uuid4()),
                    "role_id": str(role_id),
                    "policy_id": str(policy_id),
                },
            )


def downgrade() -> None:
    # Don't delete data on downgrade - it's seed data that should persist
    pass
