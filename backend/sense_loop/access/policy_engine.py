"""Policy engine for access control."""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Annotated, Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import DbSession

from .permissions import Permission

if TYPE_CHECKING:
    from sense_loop.models import Practitioner, PractitionerRole

# Import models for joinedload - must use class-bound attributes in SQLAlchemy 2.0+
from sense_loop.models import Practitioner as PractitionerModel
from sense_loop.models import PractitionerRole as PractitionerRoleModel

security = HTTPBearer()


class PolicyEngine:
    """Access control policy engine."""

    def __init__(self, db: Session):
        self.db = db

    def get_practitioner_by_id(self, practitioner_id: UUID) -> "Practitioner | None":
        """Get practitioner by ID with roles loaded."""
        stmt = (
            select(PractitionerModel)
            .where(PractitionerModel.id == practitioner_id)
            .options(
                joinedload(PractitionerModel.practitioner_roles).joinedload(
                    PractitionerRoleModel.role_definition
                ),
                joinedload(PractitionerModel.practitioner_roles).joinedload(
                    PractitionerRoleModel.organization
                ),
            )
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_practitioner_by_email(self, email: str) -> "Practitioner | None":
        """Get practitioner by email with roles loaded."""
        stmt = (
            select(PractitionerModel)
            .where(PractitionerModel.email == email)
            .options(
                joinedload(PractitionerModel.practitioner_roles).joinedload(
                    PractitionerRoleModel.role_definition
                ),
                joinedload(PractitionerModel.practitioner_roles).joinedload(
                    PractitionerRoleModel.organization
                ),
            )
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_role_for_org(
        self, practitioner: "Practitioner", organization_id: UUID
    ) -> "PractitionerRole | None":
        """Get practitioner's role in a specific organization."""
        for role in practitioner.practitioner_roles:
            if role.organization_id == organization_id and role.is_active:
                return role
        return None

    def has_permission(
        self,
        practitioner: "Practitioner",
        permission: Permission,
        organization_id: UUID | None = None,
    ) -> bool:
        """Check if practitioner has a specific permission.

        If organization_id is provided, checks permission for that org only.
        Otherwise, checks if practitioner has permission in any org.
        """
        for role in practitioner.practitioner_roles:
            if not role.is_active:
                continue
            if organization_id and role.organization_id != organization_id:
                continue

            rd = role.role_definition
            if getattr(rd, permission.value, False):
                return True

        return False

    def has_any_permission(
        self,
        practitioner: "Practitioner",
        permissions: list[Permission],
        organization_id: UUID | None = None,
    ) -> bool:
        """Check if practitioner has any of the specified permissions."""
        return any(
            self.has_permission(practitioner, p, organization_id) for p in permissions
        )

    def has_all_permissions(
        self,
        practitioner: "Practitioner",
        permissions: list[Permission],
        organization_id: UUID | None = None,
    ) -> bool:
        """Check if practitioner has all of the specified permissions."""
        return all(
            self.has_permission(practitioner, p, organization_id) for p in permissions
        )

    def can_access_patient(
        self, practitioner: "Practitioner", patient_organization_id: UUID
    ) -> bool:
        """Check if practitioner can access a patient's data."""
        role = self.get_role_for_org(practitioner, patient_organization_id)
        if not role:
            return False
        return role.role_definition.can_manage_patients

    def get_accessible_org_ids(self, practitioner: "Practitioner") -> list[UUID]:
        """Get list of organization IDs the practitioner can access."""
        return [
            role.organization_id
            for role in practitioner.practitioner_roles
            if role.is_active
        ]


def decode_practitioner_token(token: str) -> dict:
    """Decode and validate a practitioner JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        if payload.get("type") != "sl_practitioner":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )


async def get_current_practitioner(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: DbSession,
) -> "Practitioner":
    """Get the current authenticated practitioner from JWT token."""
    payload = decode_practitioner_token(credentials.credentials)
    practitioner_id = payload.get("sub")

    if not practitioner_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    engine = PolicyEngine(db)
    practitioner = engine.get_practitioner_by_id(UUID(practitioner_id))

    if not practitioner:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Practitioner not found",
        )

    if not practitioner.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
        )

    return practitioner


def require_permission(*permissions: Permission):
    """Decorator to require specific permissions for an endpoint.

    Usage:
        @router.get("/patients")
        @require_permission(Permission.MANAGE_PATIENTS)
        async def list_patients(practitioner: CurrentPractitioner):
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get practitioner from kwargs (injected by Depends)
            practitioner = kwargs.get("practitioner")
            if not practitioner:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            # Get organization_id if provided
            organization_id = kwargs.get("organization_id")

            # Check permissions
            db = kwargs.get("db")
            if not db:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database session not available",
                )

            engine = PolicyEngine(db)
            if not engine.has_any_permission(
                practitioner, list(permissions), organization_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# Type alias for dependency injection
CurrentPractitioner = Annotated["Practitioner", Depends(get_current_practitioner)]
