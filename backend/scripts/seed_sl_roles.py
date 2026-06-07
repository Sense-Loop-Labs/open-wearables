#!/usr/bin/env python3
"""Seed default Sense Loop role definitions."""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from uuid import uuid4

from sqlalchemy import select

from app.database import SessionLocal
from sense_loop.models.role_definition import DEFAULT_ROLES, RoleDefinition


def seed_roles():
    """Seed default role definitions if they don't exist."""
    db = SessionLocal()

    try:
        for role_data in DEFAULT_ROLES:
            # Check if role exists
            stmt = select(RoleDefinition).where(
                RoleDefinition.code == role_data["code"],
                RoleDefinition.organization_id.is_(None),
                RoleDefinition.is_system_role == True,  # noqa: E712
            )
            existing = db.execute(stmt).scalar_one_or_none()

            if existing:
                print(f"Role '{role_data['code']}' already exists, skipping")
                continue

            # Create role
            role = RoleDefinition(
                id=uuid4(),
                organization_id=None,  # System role
                **role_data,
            )
            db.add(role)
            print(f"Created role: {role_data['code']} ({role_data['display_name']})")

        db.commit()
        print("\nRole seeding complete!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding roles: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_roles()
