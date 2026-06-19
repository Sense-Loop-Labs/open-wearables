#!/usr/bin/env python3
"""Seed Sense Loop bootstrap organization and admin practitioner.

This script creates the initial organization and super admin practitioner
needed to access the Sense Loop clinical dashboard.

Usage: python -m scripts.init.seed_sl_admin

Environment variables (with SL_ prefix):
  SL_ADMIN_EMAIL       - Admin email (default: admin@senseloop.health)
  SL_ADMIN_PASSWORD    - Admin password (default: changeme123!)
  SL_ADMIN_FIRST_NAME  - Admin first name (default: System)
  SL_ADMIN_LAST_NAME   - Admin last name (default: Admin)
  SL_DEFAULT_ORG_NAME  - Organization name (default: Demo Clinic)
  SL_DEFAULT_ORG_SLUG  - Organization slug (default: demo-clinic)
"""

from datetime import datetime
from uuid import uuid4

from passlib.hash import pbkdf2_sha256
from sqlalchemy import select

from app.database import SessionLocal
from sense_loop.config import sl_settings
from sense_loop.models import Organization, Practitioner, PractitionerRole, RoleDefinition


def get_or_create_organization(db) -> Organization:
    """Get or create the default organization."""
    # Check if organization exists by slug
    stmt = select(Organization).where(Organization.slug == sl_settings.default_org_slug)
    org = db.execute(stmt).scalar_one_or_none()

    if org:
        print(f"Organization '{org.name}' already exists (id: {org.id})")
        return org

    # Create organization
    org = Organization(
        id=uuid4(),
        name=sl_settings.default_org_name,
        slug=sl_settings.default_org_slug,
        contact_email=sl_settings.admin_email,
        default_timezone="America/Los_Angeles",
    )
    db.add(org)
    db.flush()

    print(f"Created organization: {org.name} (id: {org.id})")
    return org


def get_super_admin_role(db) -> RoleDefinition | None:
    """Get the super_admin role definition."""
    stmt = select(RoleDefinition).where(
        RoleDefinition.code == "super_admin",
        RoleDefinition.organization_id.is_(None),
        RoleDefinition.is_system_role == True,  # noqa: E712
    )
    return db.execute(stmt).scalar_one_or_none()


def get_or_create_admin_practitioner(db, org: Organization) -> Practitioner:
    """Get or create the admin practitioner."""
    # Check if practitioner exists by email
    stmt = select(Practitioner).where(Practitioner.email == sl_settings.admin_email.lower())
    practitioner = db.execute(stmt).scalar_one_or_none()

    if practitioner:
        print(f"Practitioner '{practitioner.email}' already exists (id: {practitioner.id})")
        return practitioner

    # Create practitioner
    practitioner = Practitioner(
        id=uuid4(),
        email=sl_settings.admin_email.lower(),
        password_hash=pbkdf2_sha256.hash(sl_settings.admin_password.get_secret_value()),
        first_name=sl_settings.admin_first_name,
        last_name=sl_settings.admin_last_name,
        email_verified_at=datetime.utcnow(),
    )
    db.add(practitioner)
    db.flush()

    print(f"Created practitioner: {practitioner.email} (id: {practitioner.id})")
    return practitioner


def ensure_practitioner_role(db, practitioner: Practitioner, org: Organization, role_def: RoleDefinition) -> None:
    """Ensure the practitioner has the super_admin role in the organization."""
    # Check if role assignment exists
    stmt = select(PractitionerRole).where(
        PractitionerRole.practitioner_id == practitioner.id,
        PractitionerRole.organization_id == org.id,
    )
    existing_role = db.execute(stmt).scalar_one_or_none()

    if existing_role:
        print(f"Practitioner already has role in organization (role: {existing_role.role_definition.code})")
        return

    # Create role assignment
    role = PractitionerRole(
        id=uuid4(),
        practitioner_id=practitioner.id,
        organization_id=org.id,
        role_definition_id=role_def.id,
        is_primary=True,
        accepted_at=datetime.utcnow(),
    )
    db.add(role)
    db.flush()

    print(f"Assigned super_admin role to practitioner in organization")


def seed_sl_admin() -> None:
    """Create the bootstrap organization and admin practitioner."""
    db = SessionLocal()

    try:
        # Get super_admin role definition
        role_def = get_super_admin_role(db)
        if not role_def:
            print("ERROR: super_admin role definition not found.")
            print("Make sure migrations have been run and roles are seeded.")
            print("Run: alembic upgrade head")
            return

        # Create organization
        org = get_or_create_organization(db)

        # Create admin practitioner
        practitioner = get_or_create_admin_practitioner(db, org)

        # Ensure role assignment
        ensure_practitioner_role(db, practitioner, org, role_def)

        db.commit()

        print()
        print("=" * 60)
        print("Sense Loop Admin Bootstrap Complete!")
        print("=" * 60)
        print()
        print(f"  Dashboard URL: {sl_settings.app_base_url}/sl/login")
        print(f"  Email:         {sl_settings.admin_email}")
        print(f"  Password:      {'*' * len(sl_settings.admin_password.get_secret_value())}")
        print(f"  Organization:  {org.name}")
        print()
        print("IMPORTANT: Change the admin password after first login!")
        print()

    except Exception as e:
        db.rollback()
        print(f"Error seeding Sense Loop admin: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_sl_admin()
