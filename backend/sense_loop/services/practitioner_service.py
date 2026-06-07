"""Practitioner service - clinician CRUD operations."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from sense_loop.models import Practitioner, PractitionerRole, RoleDefinition
from sense_loop.schemas.practitioner import PractitionerCreate, PractitionerUpdate

logger = logging.getLogger(__name__)


class PractitionerService:
    """Service for practitioner management."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, practitioner_id: UUID) -> Practitioner | None:
        """Get practitioner by ID with roles loaded."""
        stmt = (
            select(Practitioner)
            .where(Practitioner.id == practitioner_id)
            .options(
                joinedload(Practitioner.practitioner_roles)
                .joinedload(PractitionerRole.role_definition),
                joinedload(Practitioner.practitioner_roles)
                .joinedload(PractitionerRole.organization),
            )
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_by_email(self, email: str) -> Practitioner | None:
        """Get practitioner by email."""
        stmt = (
            select(Practitioner)
            .where(Practitioner.email == email.lower())
            .options(
                joinedload(Practitioner.practitioner_roles)
                .joinedload(PractitionerRole.role_definition),
                joinedload(Practitioner.practitioner_roles)
                .joinedload(PractitionerRole.organization),
            )
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def list_by_organization(
        self,
        organization_id: UUID,
        *,
        is_active: bool | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Practitioner], int]:
        """List practitioners in an organization."""
        # Get practitioners with roles in this org
        stmt = (
            select(Practitioner)
            .join(PractitionerRole)
            .where(PractitionerRole.organization_id == organization_id)
            .options(
                joinedload(Practitioner.practitioner_roles)
                .joinedload(PractitionerRole.role_definition),
                joinedload(Practitioner.practitioner_roles)
                .joinedload(PractitionerRole.organization),
            )
        )

        if is_active is not None:
            stmt = stmt.where(Practitioner.is_active == is_active)

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                (Practitioner.first_name.ilike(search_pattern))
                | (Practitioner.last_name.ilike(search_pattern))
                | (Practitioner.email.ilike(search_pattern))
            )

        # Count total
        count_stmt = select(func.count(func.distinct(Practitioner.id))).select_from(
            stmt.subquery()
        )
        total = self.db.execute(count_stmt).scalar() or 0

        # Paginate
        stmt = stmt.order_by(Practitioner.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        practitioners = self.db.execute(stmt).unique().scalars().all()
        return list(practitioners), total

    def create(self, data: PractitionerCreate) -> Practitioner:
        """Create a new practitioner with organization role."""
        from passlib.hash import pbkdf2_sha256

        # Check if email already exists
        existing = self.get_by_email(data.email)
        if existing:
            raise ValueError("Email already registered")

        # Get role definition
        role_def = self._get_role_definition(data.role_code, data.organization_id)
        if not role_def:
            raise ValueError(f"Invalid role code: {data.role_code}")

        # Create practitioner
        practitioner = Practitioner(
            id=uuid4(),
            email=data.email.lower(),
            password_hash=pbkdf2_sha256.hash(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            npi_number=data.npi_number,
            credentials=data.credentials,
        )

        self.db.add(practitioner)
        self.db.flush()

        # Create role assignment
        role = PractitionerRole(
            id=uuid4(),
            practitioner_id=practitioner.id,
            organization_id=data.organization_id,
            role_definition_id=role_def.id,
            is_primary=True,
        )

        self.db.add(role)
        self.db.flush()

        logger.info(
            "Created practitioner %s in org %s with role %s",
            practitioner.id,
            data.organization_id,
            data.role_code,
        )
        return practitioner

    def update(self, practitioner: Practitioner, data: PractitionerUpdate) -> Practitioner:
        """Update a practitioner."""
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(practitioner, field, value)

        self.db.flush()

        logger.info("Updated practitioner %s", practitioner.id)
        return practitioner

    def add_to_organization(
        self,
        practitioner: Practitioner,
        organization_id: UUID,
        role_code: str,
        is_primary: bool = False,
    ) -> PractitionerRole:
        """Add practitioner to an organization with a role."""
        from datetime import datetime

        # Check if already in org
        for role in practitioner.practitioner_roles:
            if role.organization_id == organization_id:
                raise ValueError("Practitioner already in organization")

        # Get role definition
        role_def = self._get_role_definition(role_code, organization_id)
        if not role_def:
            raise ValueError(f"Invalid role code: {role_code}")

        # Create role assignment
        role = PractitionerRole(
            id=uuid4(),
            practitioner_id=practitioner.id,
            organization_id=organization_id,
            role_definition_id=role_def.id,
            is_primary=is_primary,
            accepted_at=datetime.utcnow(),
        )

        self.db.add(role)
        self.db.flush()

        logger.info(
            "Added practitioner %s to org %s with role %s",
            practitioner.id,
            organization_id,
            role_code,
        )
        return role

    def update_role(
        self,
        practitioner: Practitioner,
        organization_id: UUID,
        new_role_code: str,
    ) -> PractitionerRole | None:
        """Update practitioner's role in an organization."""
        for role in practitioner.practitioner_roles:
            if role.organization_id == organization_id:
                # Get new role definition
                role_def = self._get_role_definition(new_role_code, organization_id)
                if not role_def:
                    raise ValueError(f"Invalid role code: {new_role_code}")

                role.role_definition_id = role_def.id
                self.db.flush()

                logger.info(
                    "Updated practitioner %s role in org %s to %s",
                    practitioner.id,
                    organization_id,
                    new_role_code,
                )
                return role

        return None

    def deactivate(self, practitioner: Practitioner) -> Practitioner:
        """Deactivate a practitioner."""
        from datetime import datetime

        practitioner.is_active = False
        practitioner.deactivated_at = datetime.utcnow()

        # Deactivate all roles
        for role in practitioner.practitioner_roles:
            role.is_active = False
            role.deactivated_at = datetime.utcnow()

        self.db.flush()

        logger.info("Deactivated practitioner %s", practitioner.id)
        return practitioner

    def _get_role_definition(
        self, code: str, organization_id: UUID | None
    ) -> RoleDefinition | None:
        """Get role definition by code."""
        # First try org-specific role
        if organization_id:
            stmt = select(RoleDefinition).where(
                RoleDefinition.code == code,
                RoleDefinition.organization_id == organization_id,
                RoleDefinition.is_active == True,  # noqa: E712
            )
            role = self.db.execute(stmt).scalar_one_or_none()
            if role:
                return role

        # Fall back to system role
        stmt = select(RoleDefinition).where(
            RoleDefinition.code == code,
            RoleDefinition.organization_id.is_(None),
            RoleDefinition.is_system_role == True,  # noqa: E712
            RoleDefinition.is_active == True,  # noqa: E712
        )
        return self.db.execute(stmt).scalar_one_or_none()
