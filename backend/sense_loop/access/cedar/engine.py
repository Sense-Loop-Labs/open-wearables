"""Cedar-based authorization engine.

Provides fine-grained access control using Cedar policies, supporting
field-level permissions, time-bounded access, and break-the-glass scenarios.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from .entity_builder import build_practitioner_entity, make_entity_uid
from .models import (
    AccessPolicy,
    BreakTheGlassAccess,
    PractitionerAccessPolicy,
    RoleAccessPolicy,
)
from .policy_builder import (
    get_hidden_fields_from_policy,
    get_readonly_fields_from_policy,
)

if TYPE_CHECKING:
    from sense_loop.models import Practitioner

logger = logging.getLogger(__name__)


@dataclass
class CedarAuthorizationResult:
    """Result of a Cedar authorization check."""

    allowed: bool
    decision_reason: str
    matched_policies: list[str] = field(default_factory=list)
    hidden_fields: list[str] = field(default_factory=list)
    readonly_fields: list[str] = field(default_factory=list)
    btg_access: bool = False
    btg_access_id: UUID | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "allowed": self.allowed,
            "decision_reason": self.decision_reason,
            "matched_policies": self.matched_policies,
            "hidden_fields": self.hidden_fields,
            "readonly_fields": self.readonly_fields,
            "btg_access": self.btg_access,
            "btg_access_id": str(self.btg_access_id) if self.btg_access_id else None,
        }


class CedarEngine:
    """Cedar-based authorization engine.

    Evaluates access requests against Cedar policies stored in the database,
    supporting role-based policies, individual overrides, and break-the-glass
    emergency access.
    """

    def __init__(self, db: Session):
        """Initialize the Cedar engine.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self._policy_cache: dict[str, list[AccessPolicy]] | None = None

    def is_authorized(
        self,
        practitioner: "Practitioner",
        action: str,
        resource_type: str,
        resource_id: UUID | None,
        organization_id: UUID,
        context: dict[str, Any] | None = None,
    ) -> CedarAuthorizationResult:
        """Check if a practitioner is authorized to perform an action.

        Args:
            practitioner: The practitioner requesting access
            action: The action being performed (read, update, delete, etc.)
            resource_type: The type of resource (patient, alert, etc.)
            resource_id: The specific resource ID (None for type-level checks)
            organization_id: The organization context
            context: Additional context for policy evaluation

        Returns:
            CedarAuthorizationResult with the authorization decision
        """
        context = context or {}

        # First, check for active break-the-glass access
        btg_access = self._check_btg_access(
            practitioner.id, organization_id, resource_type, resource_id
        )
        if btg_access:
            return CedarAuthorizationResult(
                allowed=True,
                decision_reason="Break-the-glass access granted",
                matched_policies=["btg_emergency_access"],
                hidden_fields=[],
                readonly_fields=[],
                btg_access=True,
                btg_access_id=btg_access.id,
            )

        # Get all applicable policies for this practitioner and resource
        policies = self._get_applicable_policies(
            practitioner, resource_type, organization_id
        )

        if not policies:
            # No policies found - check legacy permissions as fallback
            return self._check_legacy_permissions(
                practitioner, action, resource_type, organization_id
            )

        # Evaluate policies (sorted by priority, higher first)
        sorted_policies = sorted(policies, key=lambda p: -p.priority)

        matched_policies: list[str] = []
        hidden_fields: set[str] = set()
        readonly_fields: set[str] = set()
        allowed = False
        decision_reason = "No matching permit policy found"

        for policy in sorted_policies:
            if not policy.is_active:
                continue

            rules = policy.rules
            policy_resource_type = rules.get("resource_type", "").lower()
            policy_actions = [a.lower() for a in rules.get("actions", [])]

            # Check resource type match
            if policy_resource_type and policy_resource_type != resource_type.lower():
                continue

            # Check action match
            if policy_actions and action.lower() not in policy_actions:
                continue

            # Check conditions
            if not self._evaluate_conditions(
                rules.get("conditions", {}),
                practitioner,
                organization_id,
                context,
            ):
                continue

            # Policy matches
            matched_policies.append(policy.code)

            # Collect field restrictions
            hidden_fields.update(get_hidden_fields_from_policy(policy))
            readonly_fields.update(get_readonly_fields_from_policy(policy))

            # Determine effect
            if policy.effect.lower() == "forbid":
                allowed = False
                decision_reason = f"Explicitly forbidden by policy: {policy.code}"
                break
            elif policy.effect.lower() == "permit":
                allowed = True
                decision_reason = f"Permitted by policy: {policy.code}"
                # Don't break - continue to collect field restrictions from other policies

        return CedarAuthorizationResult(
            allowed=allowed,
            decision_reason=decision_reason,
            matched_policies=matched_policies,
            hidden_fields=list(hidden_fields),
            readonly_fields=list(readonly_fields),
            btg_access=False,
            btg_access_id=None,
        )

    def _get_applicable_policies(
        self,
        practitioner: "Practitioner",
        resource_type: str,
        organization_id: UUID,
    ) -> list[AccessPolicy]:
        """Get all policies applicable to a practitioner for a resource type.

        Collects policies from:
        1. Role-based policies (via PractitionerRole -> RoleDefinition)
        2. Individual practitioner policy assignments
        3. System-wide policies

        Args:
            practitioner: The practitioner
            resource_type: The resource type
            organization_id: The organization context

        Returns:
            List of applicable AccessPolicy records
        """
        policies: list[AccessPolicy] = []
        now = datetime.now()

        # 1. Get role-based policies
        role_codes = self._get_practitioner_role_codes(practitioner, organization_id)
        if role_codes:
            stmt = (
                select(AccessPolicy)
                .join(RoleAccessPolicy)
                .join(RoleAccessPolicy.role_definition)
                .where(
                    and_(
                        RoleAccessPolicy.is_active == True,  # noqa: E712
                        AccessPolicy.is_active == True,  # noqa: E712
                        or_(
                            AccessPolicy.organization_id == organization_id,
                            AccessPolicy.organization_id.is_(None),  # System-wide
                        ),
                    )
                )
                .options(joinedload(AccessPolicy.role_policies))
            )
            # Filter by role codes in Python (easier than complex SQL)
            role_policies = self.db.execute(stmt).unique().scalars().all()
            for policy in role_policies:
                for rp in policy.role_policies:
                    if (
                        rp.is_active
                        and rp.role_definition
                        and rp.role_definition.code in role_codes
                    ):
                        policies.append(policy)
                        break

        # 2. Get individual practitioner policies
        stmt = (
            select(AccessPolicy)
            .join(PractitionerAccessPolicy)
            .where(
                and_(
                    PractitionerAccessPolicy.practitioner_id == practitioner.id,
                    PractitionerAccessPolicy.organization_id == organization_id,
                    AccessPolicy.is_active == True,  # noqa: E712
                    or_(
                        PractitionerAccessPolicy.valid_from.is_(None),
                        PractitionerAccessPolicy.valid_from <= now,
                    ),
                    or_(
                        PractitionerAccessPolicy.valid_until.is_(None),
                        PractitionerAccessPolicy.valid_until >= now,
                    ),
                )
            )
        )
        individual_policies = self.db.execute(stmt).scalars().all()
        policies.extend(individual_policies)

        # 3. Get system-wide policies (not attached to roles or practitioners)
        stmt = select(AccessPolicy).where(
            and_(
                AccessPolicy.is_active == True,  # noqa: E712
                AccessPolicy.is_system_policy == True,  # noqa: E712
                AccessPolicy.organization_id.is_(None),
            )
        )
        system_policies = self.db.execute(stmt).scalars().all()

        # Only add system policies if not already covered by role/individual policies
        existing_codes = {p.code for p in policies}
        for sp in system_policies:
            if sp.code not in existing_codes:
                policies.append(sp)

        # Filter to resource type
        resource_type_lower = resource_type.lower()
        filtered = []
        for policy in policies:
            rules = policy.rules
            policy_resource = rules.get("resource_type", "").lower()
            if not policy_resource or policy_resource == resource_type_lower:
                filtered.append(policy)

        return filtered

    def _get_practitioner_role_codes(
        self, practitioner: "Practitioner", organization_id: UUID
    ) -> list[str]:
        """Get role codes for a practitioner in an organization."""
        codes = []
        if hasattr(practitioner, "practitioner_roles"):
            for role in practitioner.practitioner_roles:
                if (
                    role.organization_id == organization_id
                    and role.is_active
                    and role.role_definition
                ):
                    codes.append(role.role_definition.code)
        return codes

    def _evaluate_conditions(
        self,
        conditions: dict[str, Any],
        practitioner: "Practitioner",
        organization_id: UUID,
        context: dict[str, Any],
    ) -> bool:
        """Evaluate policy conditions.

        Args:
            conditions: Condition dictionary from policy rules
            practitioner: The practitioner
            organization_id: The organization context
            context: Additional context

        Returns:
            True if all conditions are satisfied
        """
        if not conditions:
            return True

        # Same organization check
        if conditions.get("same_organization"):
            # The practitioner must have a role in this organization
            has_org_role = False
            if hasattr(practitioner, "practitioner_roles"):
                for role in practitioner.practitioner_roles:
                    if role.organization_id == organization_id and role.is_active:
                        has_org_role = True
                        break
            if not has_org_role:
                return False

        # Enrollment status filter (checked against context if provided)
        if "enrollment_status" in conditions:
            allowed_statuses = conditions["enrollment_status"]
            resource_status = context.get("enrollment_status")
            if resource_status and resource_status not in allowed_statuses:
                return False

        # Resource active check
        if conditions.get("resource_active"):
            is_active = context.get("is_active", True)
            if not is_active:
                return False

        return True

    def _check_btg_access(
        self,
        practitioner_id: UUID,
        organization_id: UUID,
        resource_type: str,
        resource_id: UUID | None,
    ) -> BreakTheGlassAccess | None:
        """Check for active break-the-glass access.

        Args:
            practitioner_id: The practitioner ID
            organization_id: The organization context
            resource_type: The resource type
            resource_id: The specific resource ID (optional)

        Returns:
            BreakTheGlassAccess record if active, None otherwise
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
                    BreakTheGlassAccess.resource_id.is_(None),  # Type-level BTG
                    BreakTheGlassAccess.resource_id == resource_id,  # Specific resource
                ),
            )
        )

        btg = self.db.execute(stmt).scalars().first()
        if btg:
            # Increment access count
            btg.increment_access()
            self.db.flush()

        return btg

    def _check_legacy_permissions(
        self,
        practitioner: "Practitioner",
        action: str,
        resource_type: str,
        organization_id: UUID,
    ) -> CedarAuthorizationResult:
        """Fall back to legacy permission flags.

        Used when no Cedar policies are found for a resource type.

        Args:
            practitioner: The practitioner
            action: The action
            resource_type: The resource type
            organization_id: The organization context

        Returns:
            CedarAuthorizationResult based on legacy permissions
        """
        # Map resource types to legacy permission flags
        permission_map = {
            "patient": "can_manage_patients",
            "alert": "can_manage_alerts",
            "care_plan": "can_manage_care_plans",
            "communication": "can_manage_patients",  # Messages tied to patient access
        }

        # Map actions to specific permissions
        action_permission_map = {
            ("alert", "acknowledge"): "can_acknowledge_alerts",
            ("alert", "resolve"): "can_resolve_alerts",
            ("*", "export"): "can_export_data",
        }

        # Check for action-specific permission
        action_key = (resource_type.lower(), action.lower())
        generic_key = ("*", action.lower())

        permission_attr = action_permission_map.get(action_key)
        if not permission_attr:
            permission_attr = action_permission_map.get(generic_key)
        if not permission_attr:
            permission_attr = permission_map.get(resource_type.lower())

        if not permission_attr:
            # Unknown resource type - deny by default
            return CedarAuthorizationResult(
                allowed=False,
                decision_reason=f"No policy defined for resource type: {resource_type}",
            )

        # Check permission from role
        has_permission = False
        if hasattr(practitioner, "practitioner_roles"):
            for role in practitioner.practitioner_roles:
                if (
                    role.organization_id == organization_id
                    and role.is_active
                    and role.role_definition
                ):
                    if getattr(role.role_definition, permission_attr, False):
                        has_permission = True
                        break

        if has_permission:
            return CedarAuthorizationResult(
                allowed=True,
                decision_reason=f"Legacy permission granted: {permission_attr}",
                matched_policies=["legacy_rbac"],
            )
        else:
            return CedarAuthorizationResult(
                allowed=False,
                decision_reason=f"Legacy permission denied: {permission_attr}",
            )

    def get_query_filter(
        self,
        practitioner: "Practitioner",
        resource_type: str,
        organization_id: UUID,
    ) -> str:
        """Generate SQL WHERE clause for list queries.

        Args:
            practitioner: The practitioner
            resource_type: The resource type to filter
            organization_id: The organization context

        Returns:
            SQL WHERE clause string
        """
        # Import here to avoid circular dependency
        from .query_filter import QueryFilterBuilder

        builder = QueryFilterBuilder(self.db)
        return builder.build_filter(practitioner, resource_type, organization_id)

    def filter_response_fields(
        self,
        data: dict | list,
        practitioner: "Practitioner",
        resource_type: str,
        organization_id: UUID,
    ) -> dict | list:
        """Filter response fields based on policies.

        Args:
            data: Response data (dict or list of dicts)
            practitioner: The practitioner
            resource_type: The resource type
            organization_id: The organization context

        Returns:
            Filtered data with hidden fields removed
        """
        # Import here to avoid circular dependency
        from .field_filter import FieldFilter

        filter_instance = FieldFilter(self.db)
        return filter_instance.filter_fields(
            data, practitioner, resource_type, organization_id
        )

    def invalidate_cache(
        self,
        practitioner_id: UUID | None = None,
        organization_id: UUID | None = None,
    ) -> None:
        """Invalidate the policy cache.

        Args:
            practitioner_id: Optional practitioner to invalidate
            organization_id: Optional organization to invalidate
        """
        # For now, just clear the entire cache
        # A more sophisticated implementation could use Redis
        self._policy_cache = None
        logger.debug(
            "Policy cache invalidated",
            extra={
                "practitioner_id": str(practitioner_id) if practitioner_id else None,
                "organization_id": str(organization_id) if organization_id else None,
            },
        )
