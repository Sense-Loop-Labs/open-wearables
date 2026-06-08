"""Break-the-glass emergency access management.

Provides functionality for emergency access to patient data when normal
authorization would deny access. All BTG access is fully audited and
time-limited.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .models import BreakTheGlassAccess

if TYPE_CHECKING:
    from sense_loop.models import Practitioner

logger = logging.getLogger(__name__)


class EmergencyType(StrEnum):
    """Types of emergency access scenarios."""

    MEDICAL_EMERGENCY = "medical_emergency"
    SYSTEM_OUTAGE = "system_outage"
    DISASTER_RECOVERY = "disaster_recovery"
    CRITICAL_CARE = "critical_care"
    LIFE_THREATENING = "life_threatening"
    OTHER = "other"


@dataclass
class BTGActivationResult:
    """Result of a break-the-glass activation attempt."""

    success: bool
    btg_access_id: UUID | None
    message: str
    expires_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "success": self.success,
            "btg_access_id": str(self.btg_access_id) if self.btg_access_id else None,
            "message": self.message,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class BTGRevocationResult:
    """Result of a break-the-glass revocation attempt."""

    success: bool
    message: str
    access_count: int  # Number of times access was used


class BreakTheGlassManager:
    """Manages break-the-glass emergency access.

    Handles activation, revocation, and auditing of emergency access.
    Provides hooks for supervisor notification.
    """

    # Default BTG duration in hours
    DEFAULT_DURATION_HOURS = 4

    # Maximum BTG duration in hours
    MAX_DURATION_HOURS = 24

    # Minimum reason length
    MIN_REASON_LENGTH = 20

    def __init__(self, db: Session):
        """Initialize the BTG manager.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self._notification_hooks: list[callable] = []

    def activate(
        self,
        practitioner: "Practitioner",
        organization_id: UUID,
        resource_type: str,
        reason: str,
        emergency_type: EmergencyType | str,
        resource_id: UUID | None = None,
        duration_hours: int | None = None,
    ) -> BTGActivationResult:
        """Activate break-the-glass access.

        Args:
            practitioner: The practitioner requesting access
            organization_id: The organization context
            resource_type: The type of resource to access
            reason: Required justification (minimum 20 characters)
            emergency_type: Type of emergency
            resource_id: Specific resource ID (None for type-level access)
            duration_hours: Access duration (default: 4 hours)

        Returns:
            BTGActivationResult with success status and details
        """
        # Validate reason
        if len(reason.strip()) < self.MIN_REASON_LENGTH:
            return BTGActivationResult(
                success=False,
                btg_access_id=None,
                message=f"Reason must be at least {self.MIN_REASON_LENGTH} characters",
                expires_at=None,
            )

        # Validate emergency type
        if isinstance(emergency_type, str):
            try:
                emergency_type = EmergencyType(emergency_type)
            except ValueError:
                emergency_type = EmergencyType.OTHER

        # Validate duration
        duration = duration_hours or self.DEFAULT_DURATION_HOURS
        if duration > self.MAX_DURATION_HOURS:
            duration = self.MAX_DURATION_HOURS

        # Check for existing active BTG access
        existing = self._get_active_btg(
            practitioner.id, organization_id, resource_type, resource_id
        )
        if existing:
            return BTGActivationResult(
                success=False,
                btg_access_id=existing.id,
                message="Active break-the-glass access already exists",
                expires_at=existing.expires_at,
            )

        # Check practitioner has a role in this organization
        has_org_role = False
        if hasattr(practitioner, "practitioner_roles"):
            for role in practitioner.practitioner_roles:
                if role.organization_id == organization_id and role.is_active:
                    has_org_role = True
                    break

        if not has_org_role:
            return BTGActivationResult(
                success=False,
                btg_access_id=None,
                message="Practitioner does not have a role in this organization",
                expires_at=None,
            )

        # Create BTG access record
        now = datetime.now()
        expires_at = now + timedelta(hours=duration)

        btg_access = BreakTheGlassAccess(
            practitioner_id=practitioner.id,
            organization_id=organization_id,
            resource_type=resource_type.lower(),
            resource_id=resource_id,
            reason=reason.strip(),
            emergency_type=emergency_type.value,
            activated_at=now,
            expires_at=expires_at,
        )

        self.db.add(btg_access)
        self.db.flush()

        # Log activation
        logger.warning(
            "Break-the-glass access activated",
            extra={
                "btg_access_id": str(btg_access.id),
                "practitioner_id": str(practitioner.id),
                "organization_id": str(organization_id),
                "resource_type": resource_type,
                "resource_id": str(resource_id) if resource_id else None,
                "emergency_type": emergency_type.value,
                "expires_at": expires_at.isoformat(),
            },
        )

        # Notify supervisors
        self._notify_supervisors(
            event="btg_activated",
            btg_access=btg_access,
            practitioner=practitioner,
        )

        return BTGActivationResult(
            success=True,
            btg_access_id=btg_access.id,
            message="Break-the-glass access granted",
            expires_at=expires_at,
        )

    def revoke(
        self,
        btg_access_id: UUID,
        revoked_by: "Practitioner",
        reason: str | None = None,
    ) -> BTGRevocationResult:
        """Revoke break-the-glass access.

        Args:
            btg_access_id: The BTG access ID to revoke
            revoked_by: The practitioner revoking access
            reason: Optional reason for revocation

        Returns:
            BTGRevocationResult with success status
        """
        btg_access = self.db.get(BreakTheGlassAccess, btg_access_id)

        if not btg_access:
            return BTGRevocationResult(
                success=False,
                message="Break-the-glass access not found",
                access_count=0,
            )

        if btg_access.revoked_at:
            return BTGRevocationResult(
                success=False,
                message="Break-the-glass access already revoked",
                access_count=btg_access.access_count,
            )

        # Revoke the access
        btg_access.revoked_at = datetime.now()
        btg_access.revoked_by_id = revoked_by.id
        btg_access.revocation_reason = reason

        self.db.flush()

        # Log revocation
        logger.info(
            "Break-the-glass access revoked",
            extra={
                "btg_access_id": str(btg_access_id),
                "revoked_by_id": str(revoked_by.id),
                "access_count": btg_access.access_count,
                "reason": reason,
            },
        )

        # Notify supervisors
        self._notify_supervisors(
            event="btg_revoked",
            btg_access=btg_access,
            practitioner=revoked_by,
        )

        return BTGRevocationResult(
            success=True,
            message="Break-the-glass access revoked",
            access_count=btg_access.access_count,
        )

    def get_active_access(
        self,
        practitioner_id: UUID,
        organization_id: UUID,
    ) -> list[BreakTheGlassAccess]:
        """Get all active BTG access for a practitioner.

        Args:
            practitioner_id: The practitioner ID
            organization_id: The organization context

        Returns:
            List of active BTG access records
        """
        now = datetime.now()

        stmt = select(BreakTheGlassAccess).where(
            and_(
                BreakTheGlassAccess.practitioner_id == practitioner_id,
                BreakTheGlassAccess.organization_id == organization_id,
                BreakTheGlassAccess.activated_at <= now,
                BreakTheGlassAccess.expires_at >= now,
                BreakTheGlassAccess.revoked_at.is_(None),
            )
        )

        return list(self.db.execute(stmt).scalars().all())

    def get_organization_btg_history(
        self,
        organization_id: UUID,
        include_active: bool = True,
        include_expired: bool = True,
        include_revoked: bool = True,
        limit: int = 100,
    ) -> list[BreakTheGlassAccess]:
        """Get BTG access history for an organization.

        Args:
            organization_id: The organization ID
            include_active: Include currently active access
            include_expired: Include expired access
            include_revoked: Include revoked access
            limit: Maximum number of records

        Returns:
            List of BTG access records
        """
        now = datetime.now()
        conditions = [BreakTheGlassAccess.organization_id == organization_id]

        status_conditions = []
        if include_active:
            status_conditions.append(
                and_(
                    BreakTheGlassAccess.activated_at <= now,
                    BreakTheGlassAccess.expires_at >= now,
                    BreakTheGlassAccess.revoked_at.is_(None),
                )
            )
        if include_expired:
            status_conditions.append(
                and_(
                    BreakTheGlassAccess.expires_at < now,
                    BreakTheGlassAccess.revoked_at.is_(None),
                )
            )
        if include_revoked:
            status_conditions.append(BreakTheGlassAccess.revoked_at.is_not(None))

        if status_conditions:
            conditions.append(or_(*status_conditions))

        stmt = (
            select(BreakTheGlassAccess)
            .where(and_(*conditions))
            .order_by(BreakTheGlassAccess.activated_at.desc())
            .limit(limit)
        )

        return list(self.db.execute(stmt).scalars().all())

    def register_notification_hook(self, hook: callable) -> None:
        """Register a hook for BTG event notifications.

        The hook will be called with:
        - event: str ("btg_activated" or "btg_revoked")
        - btg_access: BreakTheGlassAccess record
        - practitioner: Practitioner who triggered the event

        Args:
            hook: Callable to invoke on BTG events
        """
        self._notification_hooks.append(hook)

    def _notify_supervisors(
        self,
        event: str,
        btg_access: BreakTheGlassAccess,
        practitioner: "Practitioner",
    ) -> None:
        """Notify supervisors of a BTG event.

        Args:
            event: Event type ("btg_activated" or "btg_revoked")
            btg_access: The BTG access record
            practitioner: The practitioner involved
        """
        for hook in self._notification_hooks:
            try:
                hook(event, btg_access, practitioner)
            except Exception as e:
                logger.error(
                    f"BTG notification hook failed: {e}",
                    extra={
                        "event": event,
                        "btg_access_id": str(btg_access.id),
                    },
                )

    def _get_active_btg(
        self,
        practitioner_id: UUID,
        organization_id: UUID,
        resource_type: str,
        resource_id: UUID | None,
    ) -> BreakTheGlassAccess | None:
        """Get existing active BTG access.

        Args:
            practitioner_id: The practitioner ID
            organization_id: The organization ID
            resource_type: The resource type
            resource_id: The specific resource ID (optional)

        Returns:
            Active BTG access if found, None otherwise
        """
        now = datetime.now()

        stmt = select(BreakTheGlassAccess).where(
            and_(
                BreakTheGlassAccess.practitioner_id == practitioner_id,
                BreakTheGlassAccess.organization_id == organization_id,
                BreakTheGlassAccess.resource_type == resource_type.lower(),
                BreakTheGlassAccess.activated_at <= now,
                BreakTheGlassAccess.expires_at >= now,
                BreakTheGlassAccess.revoked_at.is_(None),
                or_(
                    BreakTheGlassAccess.resource_id.is_(None),
                    BreakTheGlassAccess.resource_id == resource_id,
                ),
            )
        )

        return self.db.execute(stmt).scalars().first()

    def cleanup_expired(self) -> int:
        """Mark expired BTG access (for audit completeness).

        This is a maintenance task that should be run periodically.
        Note: Expired access is already not usable, this is just for cleanup.

        Returns:
            Number of expired records found
        """
        now = datetime.now()

        stmt = select(BreakTheGlassAccess).where(
            and_(
                BreakTheGlassAccess.expires_at < now,
                BreakTheGlassAccess.revoked_at.is_(None),
            )
        )

        expired = list(self.db.execute(stmt).scalars().all())

        # We don't actually modify expired records - they're kept for audit
        # Just log them
        if expired:
            logger.info(
                f"Found {len(expired)} expired BTG access records",
                extra={"expired_ids": [str(e.id) for e in expired]},
            )

        return len(expired)
