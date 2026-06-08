"""Policy engine for access control."""

from __future__ import annotations

import logging
from functools import wraps
from typing import TYPE_CHECKING, Annotated, Any, Callable
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
logger = logging.getLogger(__name__)


class PolicyEngine:
    """Access control policy engine.

    Supports both legacy permission-flag-based authorization and Cedar-based
    authorization. In parallel mode, both systems are evaluated and any
    discrepancies are logged.
    """

    def __init__(self, db: Session):
        self.db = db
        self._cedar_engine = None

    def _get_cedar_engine(self) -> "CedarEngine":
        """Get or create the Cedar engine instance."""
        if self._cedar_engine is None:
            from .cedar import CedarEngine
            self._cedar_engine = CedarEngine(self.db)
        return self._cedar_engine

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

    # =========================================================================
    # Cedar Integration Methods
    # =========================================================================

    def is_authorized_cedar(
        self,
        practitioner: "Practitioner",
        action: str,
        resource_type: str,
        resource_id: UUID | None,
        organization_id: UUID,
        context: dict[str, Any] | None = None,
    ) -> "CedarAuthorizationResult":
        """Check authorization using Cedar policies.

        Args:
            practitioner: The practitioner requesting access
            action: The action (read, update, delete, etc.)
            resource_type: The resource type (patient, alert, etc.)
            resource_id: Specific resource ID (None for type-level)
            organization_id: Organization context
            context: Additional context for policy evaluation

        Returns:
            CedarAuthorizationResult with decision details
        """
        from .cedar import CedarAuthorizationResult

        cedar = self._get_cedar_engine()
        return cedar.is_authorized(
            practitioner, action, resource_type, resource_id, organization_id, context
        )

    def is_authorized_with_parallel_check(
        self,
        practitioner: "Practitioner",
        permission: Permission,
        organization_id: UUID,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Check authorization with parallel Cedar evaluation.

        When parallel mode is enabled, evaluates both legacy RBAC and Cedar,
        logs any discrepancies, but returns the legacy decision.

        Args:
            practitioner: The practitioner
            permission: The legacy permission to check
            organization_id: Organization context
            action: Cedar action (derived from permission if not provided)
            resource_type: Cedar resource type (derived from permission if not provided)
            resource_id: Specific resource ID
            context: Additional context

        Returns:
            Boolean authorization decision (legacy decision in parallel mode)
        """
        from sense_loop.config import sl_settings

        # Legacy decision
        legacy_allowed = self.has_permission(practitioner, permission, organization_id)

        # Skip Cedar check if not enabled
        if not sl_settings.use_cedar_auth and not sl_settings.cedar_parallel_mode:
            return legacy_allowed

        # Derive Cedar action and resource type from permission if not provided
        if action is None:
            action = self._permission_to_action(permission)
        if resource_type is None:
            resource_type = self._permission_to_resource_type(permission)

        # Cedar decision
        cedar_result = self.is_authorized_cedar(
            practitioner, action, resource_type, resource_id, organization_id, context
        )

        # Log discrepancies in parallel mode
        if sl_settings.cedar_parallel_mode:
            if legacy_allowed != cedar_result.allowed:
                logger.warning(
                    "Policy decision mismatch",
                    extra={
                        "practitioner_id": str(practitioner.id),
                        "organization_id": str(organization_id),
                        "permission": permission.value,
                        "action": action,
                        "resource_type": resource_type,
                        "resource_id": str(resource_id) if resource_id else None,
                        "legacy_allowed": legacy_allowed,
                        "cedar_allowed": cedar_result.allowed,
                        "cedar_reason": cedar_result.decision_reason,
                        "cedar_policies": cedar_result.matched_policies,
                    },
                )

        # Return Cedar decision if fully enabled, otherwise legacy
        if sl_settings.use_cedar_auth and not sl_settings.cedar_parallel_mode:
            return cedar_result.allowed

        return legacy_allowed

    def filter_response_fields(
        self,
        data: dict | list,
        practitioner: "Practitioner",
        resource_type: str,
        organization_id: UUID,
    ) -> dict | list:
        """Filter response fields based on Cedar policies.

        Args:
            data: Response data to filter
            practitioner: The practitioner
            resource_type: The resource type
            organization_id: Organization context

        Returns:
            Filtered data with hidden fields removed
        """
        from sense_loop.config import sl_settings

        if not sl_settings.use_cedar_auth:
            return data

        cedar = self._get_cedar_engine()
        return cedar.filter_response_fields(
            data, practitioner, resource_type, organization_id
        )

    def get_query_filter(
        self,
        practitioner: "Practitioner",
        resource_type: str,
        organization_id: UUID,
    ) -> str:
        """Get SQL WHERE clause for query filtering.

        Args:
            practitioner: The practitioner
            resource_type: The resource type
            organization_id: Organization context

        Returns:
            SQL WHERE clause string
        """
        cedar = self._get_cedar_engine()
        return cedar.get_query_filter(practitioner, resource_type, organization_id)

    def _permission_to_action(self, permission: Permission) -> str:
        """Map legacy permission to Cedar action."""
        action_map = {
            Permission.MANAGE_PATIENTS: "read",
            Permission.MANAGE_ALERTS: "read",
            Permission.RESOLVE_ALERTS: "resolve",
            Permission.ACKNOWLEDGE_ALERTS: "acknowledge",
            Permission.MANAGE_CARE_PLANS: "read",
            Permission.MANAGE_CLINICIANS: "read",
            Permission.MANAGE_ORG_SETTINGS: "read",
            Permission.VIEW_AUDIT_LOGS: "read",
            Permission.MANAGE_ALERT_PROTOCOLS: "read",
            Permission.EXPORT_DATA: "export",
        }
        return action_map.get(permission, "read")

    def _permission_to_resource_type(self, permission: Permission) -> str:
        """Map legacy permission to Cedar resource type."""
        resource_map = {
            Permission.MANAGE_PATIENTS: "patient",
            Permission.MANAGE_ALERTS: "alert",
            Permission.RESOLVE_ALERTS: "alert",
            Permission.ACKNOWLEDGE_ALERTS: "alert",
            Permission.MANAGE_CARE_PLANS: "care_plan",
            Permission.MANAGE_CLINICIANS: "practitioner",
            Permission.MANAGE_ORG_SETTINGS: "organization",
            Permission.VIEW_AUDIT_LOGS: "audit_log",
            Permission.MANAGE_ALERT_PROTOCOLS: "alert_protocol",
            Permission.EXPORT_DATA: "patient",
        }
        return resource_map.get(permission, "resource")


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
