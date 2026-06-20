#!/usr/bin/env python3
"""Seed default Sense Loop access policies and role-policy associations.

This script creates the system access policies and links them to roles.
Must be run AFTER seed_sl_roles.py.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from uuid import UUID

from sqlalchemy import select

from app.database import SessionLocal
from sense_loop.models import AccessPolicy, RoleAccessPolicy, RoleDefinition


# Access policies - these define permissions for specific resource types
ACCESS_POLICIES = [
    {
        "id": UUID("8500c19c-0306-4656-b07c-16a28071f287"),
        "code": "alert_acknowledge_only",
        "name": "Alert Acknowledge Only",
        "description": "Can read and acknowledge alerts but not resolve them",
        "rules": {
            "actions": ["read", "acknowledge"],
            "conditions": {"same_organization": True},
            "hidden_fields": [],
            "resource_type": "alert",
            "readonly_fields": [],
        },
        "effect": "permit",
        "priority": 50,
        "is_system_policy": True,
    },
    {
        "id": UUID("fcd40d6b-1312-4146-971c-8146ffa14b36"),
        "code": "communication_read_only",
        "name": "Communication Read Only",
        "description": "Can read but not send communications",
        "rules": {
            "actions": ["read"],
            "conditions": {"same_organization": True},
            "hidden_fields": [],
            "resource_type": "communication",
            "readonly_fields": [],
        },
        "effect": "permit",
        "priority": 50,
        "is_system_policy": True,
    },
    {
        "id": UUID("dc993503-1249-4eff-a095-4c1bc7d4db85"),
        "code": "patient_read_only",
        "name": "Patient Read Only",
        "description": "Read-only access to patient records within the organization",
        "rules": {
            "actions": ["read"],
            "conditions": {"same_organization": True},
            "hidden_fields": ["password_hash", "activation_code"],
            "resource_type": "patient",
            "readonly_fields": [],
        },
        "effect": "permit",
        "priority": 50,
        "is_system_policy": True,
    },
    {
        "id": UUID("d2d23557-189b-4e6c-b2c7-d5da75f8206b"),
        "code": "alert_resolve",
        "name": "Alert Resolve Access",
        "description": "Can resolve alerts (in addition to acknowledge)",
        "rules": {
            "actions": ["resolve"],
            "conditions": {"same_organization": True},
            "hidden_fields": [],
            "resource_type": "alert",
            "readonly_fields": [],
        },
        "effect": "permit",
        "priority": 75,
        "is_system_policy": True,
    },
    {
        "id": UUID("a995635d-32a3-4b66-82dc-9ef3e442ebe5"),
        "code": "alert_full_access",
        "name": "Alert Full Access",
        "description": "Full access to manage, acknowledge, and resolve alerts",
        "rules": {
            "actions": ["read", "create", "update", "acknowledge", "resolve"],
            "conditions": {"same_organization": True},
            "hidden_fields": [],
            "resource_type": "alert",
            "readonly_fields": [],
        },
        "effect": "permit",
        "priority": 100,
        "is_system_policy": True,
    },
    {
        "id": UUID("75d08429-fe01-48ac-a496-785762750f44"),
        "code": "alert_protocol_management",
        "name": "Alert Protocol Management",
        "description": "Can create and update alert protocols",
        "rules": {
            "actions": ["read", "create", "update", "delete"],
            "conditions": {"same_organization": True},
            "hidden_fields": [],
            "resource_type": "alert_protocol",
            "readonly_fields": [],
        },
        "effect": "permit",
        "priority": 100,
        "is_system_policy": True,
    },
    {
        "id": UUID("b68bf459-527d-48aa-b1f7-8e8a35912b05"),
        "code": "audit_log_access",
        "name": "Audit Log Access",
        "description": "Can view audit logs for compliance",
        "rules": {
            "actions": ["read"],
            "conditions": {"same_organization": True},
            "hidden_fields": [],
            "resource_type": "audit_log",
            "readonly_fields": [],
        },
        "effect": "permit",
        "priority": 100,
        "is_system_policy": True,
    },
    {
        "id": UUID("148023f2-2464-406f-965c-a1399f0dd54f"),
        "code": "care_plan_full_access",
        "name": "Care Plan Full Access",
        "description": "Full read/write access to care plans",
        "rules": {
            "actions": ["read", "create", "update", "delete"],
            "conditions": {"same_organization": True},
            "hidden_fields": [],
            "resource_type": "care_plan",
            "readonly_fields": [],
        },
        "effect": "permit",
        "priority": 100,
        "is_system_policy": True,
    },
    {
        "id": UUID("424497a2-242b-410b-ba0b-11b9d2c92569"),
        "code": "clinician_management",
        "name": "Clinician Management",
        "description": "Can invite, update, and deactivate clinicians",
        "rules": {
            "actions": ["read", "create", "update", "delete", "invite"],
            "conditions": {"same_organization": True},
            "hidden_fields": ["password_hash", "password_reset_token"],
            "resource_type": "practitioner",
            "readonly_fields": [],
        },
        "effect": "permit",
        "priority": 100,
        "is_system_policy": True,
    },
    {
        "id": UUID("3ae18192-8f48-42ee-9856-e513ef7a8c77"),
        "code": "communication_full_access",
        "name": "Communication Full Access",
        "description": "Can read, create, and send communications",
        "rules": {
            "actions": ["read", "create", "send"],
            "conditions": {"same_organization": True},
            "hidden_fields": [],
            "resource_type": "communication",
            "readonly_fields": [],
        },
        "effect": "permit",
        "priority": 100,
        "is_system_policy": True,
    },
    {
        "id": UUID("20b12d95-52f0-4de1-8f5d-bdc0d3261609"),
        "code": "data_export",
        "name": "Data Export Access",
        "description": "Can export patient and clinical data",
        "rules": {
            "actions": ["export"],
            "conditions": {"same_organization": True},
            "hidden_fields": [],
            "resource_type": "patient",
            "readonly_fields": [],
        },
        "effect": "permit",
        "priority": 100,
        "is_system_policy": True,
    },
    {
        "id": UUID("0fd2e3b9-8ce3-4ccb-b304-779d0e38d5f4"),
        "code": "org_settings_management",
        "name": "Organization Settings Management",
        "description": "Can update organization settings",
        "rules": {
            "actions": ["read", "update"],
            "conditions": {"same_organization": True},
            "hidden_fields": [],
            "resource_type": "organization",
            "readonly_fields": ["id", "created_at"],
        },
        "effect": "permit",
        "priority": 100,
        "is_system_policy": True,
    },
    {
        "id": UUID("f919e9dc-eea4-40b4-9194-0c548f7d024f"),
        "code": "patient_full_access",
        "name": "Patient Full Access",
        "description": "Full read/write access to patient records within the organization",
        "rules": {
            "actions": ["read", "create", "update", "delete"],
            "conditions": {"same_organization": True},
            "hidden_fields": ["password_hash"],
            "resource_type": "patient",
            "readonly_fields": [],
        },
        "effect": "permit",
        "priority": 100,
        "is_system_policy": True,
    },
]


# Role-to-policy mappings: role_code -> list of policy_codes
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


def seed_access_policies(db) -> int:
    """Seed access policies. Returns count of policies created."""
    created = 0
    for data in ACCESS_POLICIES:
        # Check by code (not ID) since migration uses random UUIDs
        stmt = select(AccessPolicy).where(
            AccessPolicy.code == data["code"],
            AccessPolicy.organization_id.is_(None),  # System policies
        )
        existing = db.execute(stmt).scalar_one_or_none()

        if existing:
            print(f"  Access policy '{data['code']}' already exists, skipping")
            continue

        policy = AccessPolicy(
            id=data["id"],
            organization_id=None,  # System-wide policy
            code=data["code"],
            name=data["name"],
            description=data["description"],
            rules=data["rules"],
            effect=data["effect"],
            priority=data["priority"],
            is_system_policy=data["is_system_policy"],
            is_active=True,
        )
        db.add(policy)
        print(f"  Created access policy: {data['name']}")
        created += 1

    return created


def seed_role_policy_associations(db) -> int:
    """Seed role-to-policy associations. Returns count created."""
    created = 0

    # Build lookup maps
    policy_map = {}
    for policy in db.execute(select(AccessPolicy)).scalars().all():
        policy_map[policy.code] = policy.id

    role_map = {}
    for role in db.execute(
        select(RoleDefinition).where(
            RoleDefinition.organization_id.is_(None),
            RoleDefinition.is_system_role == True,  # noqa: E712
        )
    ).scalars().all():
        role_map[role.code] = role.id

    for role_code, policy_codes in ROLE_POLICY_MAPPINGS.items():
        role_id = role_map.get(role_code)
        if not role_id:
            print(f"  Warning: Role '{role_code}' not found, skipping its policies")
            continue

        for policy_code in policy_codes:
            policy_id = policy_map.get(policy_code)
            if not policy_id:
                print(f"  Warning: Policy '{policy_code}' not found, skipping")
                continue

            # Check if association exists
            stmt = select(RoleAccessPolicy).where(
                RoleAccessPolicy.role_definition_id == role_id,
                RoleAccessPolicy.access_policy_id == policy_id,
            )
            existing = db.execute(stmt).scalar_one_or_none()

            if existing:
                continue

            # Create association
            from uuid import uuid4

            assoc = RoleAccessPolicy(
                id=uuid4(),
                role_definition_id=role_id,
                access_policy_id=policy_id,
            )
            db.add(assoc)
            created += 1

    if created > 0:
        print(f"  Created {created} role-policy associations")
    else:
        print("  All role-policy associations already exist")

    return created


def seed_all() -> None:
    """Seed all access policies and associations."""
    db = SessionLocal()

    try:
        print("Seeding access policies...")
        policy_count = seed_access_policies(db)

        print("Seeding role-policy associations...")
        assoc_count = seed_role_policy_associations(db)

        db.commit()

        print()
        print("Access policy seeding complete!")
        print(f"  Access policies: {policy_count} created")
        print(f"  Role associations: {assoc_count} created")

    except Exception as e:
        db.rollback()
        print(f"Error seeding access policies: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_all()
