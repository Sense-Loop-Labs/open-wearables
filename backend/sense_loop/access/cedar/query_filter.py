"""Generate SQL WHERE clauses from Cedar policies.

This module builds SQL query filters based on the applicable policies
for a practitioner, enabling efficient list queries that only return
accessible resources.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .models import AccessPolicy, PractitionerAccessPolicy, RoleAccessPolicy

if TYPE_CHECKING:
    from sense_loop.models import Practitioner

logger = logging.getLogger(__name__)


class QueryFilterBuilder:
    """Builds SQL WHERE clauses from Cedar policies.

    Translates policy conditions into SQL clauses that can be applied
    to list queries, ensuring practitioners only see resources they
    have access to.
    """

    def __init__(self, db: Session):
        """Initialize the query filter builder.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def build_filter(
        self,
        practitioner: "Practitioner",
        resource_type: str,
        organization_id: UUID,
    ) -> str:
        """Build a SQL WHERE clause for filtering resources.

        Args:
            practitioner: The practitioner requesting access
            resource_type: The resource type to filter
            organization_id: The organization context

        Returns:
            SQL WHERE clause string (without the WHERE keyword)
        """
        policies = self._get_applicable_policies(
            practitioner, resource_type, organization_id
        )

        if not policies:
            # No policies - fall back to organization check
            return f"organization_id = '{organization_id}'"

        # Build conditions from policies
        conditions = self._build_conditions_from_policies(
            policies, practitioner, organization_id
        )

        if not conditions:
            # No conditions generated - allow all in org
            return f"organization_id = '{organization_id}'"

        # Combine conditions with OR (any matching policy permits access)
        combined = " OR ".join(f"({c})" for c in conditions)

        # Always scope to organization
        return f"organization_id = '{organization_id}' AND ({combined})"

    def build_sqlalchemy_filter(
        self,
        practitioner: "Practitioner",
        resource_type: str,
        organization_id: UUID,
        model_class: type,
    ) -> Any:
        """Build a SQLAlchemy filter expression.

        Args:
            practitioner: The practitioner requesting access
            resource_type: The resource type to filter
            organization_id: The organization context
            model_class: The SQLAlchemy model class

        Returns:
            SQLAlchemy filter expression
        """
        policies = self._get_applicable_policies(
            practitioner, resource_type, organization_id
        )

        # Base filter - always scope to organization
        base_filter = model_class.organization_id == organization_id

        if not policies:
            return base_filter

        # Build SQLAlchemy conditions from policies
        policy_filters = []

        for policy in policies:
            if not policy.is_active or policy.effect.lower() != "permit":
                continue

            rules = policy.rules
            conditions = rules.get("conditions", {})

            filter_parts = []

            # Enrollment status filter
            if "enrollment_status" in conditions:
                statuses = conditions["enrollment_status"]
                if statuses and hasattr(model_class, "enrollment_status"):
                    if len(statuses) == 1:
                        filter_parts.append(
                            model_class.enrollment_status == statuses[0]
                        )
                    else:
                        filter_parts.append(
                            model_class.enrollment_status.in_(statuses)
                        )

            # Resource active filter
            if conditions.get("resource_active"):
                if hasattr(model_class, "is_active"):
                    filter_parts.append(model_class.is_active == True)  # noqa: E712

            # Custom resource attribute filters
            if "resource_attrs" in conditions:
                for attr, value in conditions["resource_attrs"].items():
                    if hasattr(model_class, attr):
                        model_attr = getattr(model_class, attr)
                        if isinstance(value, list):
                            filter_parts.append(model_attr.in_(value))
                        else:
                            filter_parts.append(model_attr == value)

            if filter_parts:
                policy_filters.append(and_(*filter_parts))
            else:
                # Policy with no conditions - permits all
                policy_filters.append(True)

        if policy_filters:
            return and_(base_filter, or_(*policy_filters))
        else:
            return base_filter

    def _build_conditions_from_policies(
        self,
        policies: list[AccessPolicy],
        practitioner: "Practitioner",
        organization_id: UUID,
    ) -> list[str]:
        """Build SQL condition strings from policies.

        Args:
            policies: List of applicable policies
            practitioner: The practitioner
            organization_id: The organization context

        Returns:
            List of SQL condition strings
        """
        conditions = []

        for policy in policies:
            if not policy.is_active:
                continue

            # Only process permit policies for query filters
            if policy.effect.lower() != "permit":
                continue

            rules = policy.rules
            policy_conditions = rules.get("conditions", {})

            parts = []

            # Enrollment status filter
            if "enrollment_status" in policy_conditions:
                statuses = policy_conditions["enrollment_status"]
                if statuses:
                    status_list = ", ".join(f"'{s}'" for s in statuses)
                    parts.append(f"enrollment_status IN ({status_list})")

            # Resource active filter
            if policy_conditions.get("resource_active"):
                parts.append("is_active = true")

            # Custom resource attribute filters
            if "resource_attrs" in policy_conditions:
                for attr, value in policy_conditions["resource_attrs"].items():
                    if isinstance(value, bool):
                        parts.append(f"{attr} = {str(value).lower()}")
                    elif isinstance(value, (int, float)):
                        parts.append(f"{attr} = {value}")
                    elif isinstance(value, str):
                        parts.append(f"{attr} = '{value}'")
                    elif isinstance(value, list):
                        if all(isinstance(v, str) for v in value):
                            value_list = ", ".join(f"'{v}'" for v in value)
                            parts.append(f"{attr} IN ({value_list})")
                        else:
                            value_list = ", ".join(str(v) for v in value)
                            parts.append(f"{attr} IN ({value_list})")

            if parts:
                conditions.append(" AND ".join(parts))
            else:
                # No specific conditions - this policy permits all in org
                conditions.append("1 = 1")  # Always true

        return conditions

    def _get_applicable_policies(
        self,
        practitioner: "Practitioner",
        resource_type: str,
        organization_id: UUID,
    ) -> list[AccessPolicy]:
        """Get applicable policies for query filtering.

        Args:
            practitioner: The practitioner
            resource_type: The resource type
            organization_id: The organization context

        Returns:
            List of applicable AccessPolicy records
        """
        policies: list[AccessPolicy] = []
        now = datetime.now()
        resource_type_lower = resource_type.lower()

        # Get role codes for this practitioner
        role_codes = []
        if hasattr(practitioner, "practitioner_roles"):
            for role in practitioner.practitioner_roles:
                if (
                    role.organization_id == organization_id
                    and role.is_active
                    and role.role_definition
                ):
                    role_codes.append(role.role_definition.code)

        # Query for role-based policies
        if role_codes:
            from sense_loop.models import RoleDefinition

            stmt = (
                select(AccessPolicy)
                .join(RoleAccessPolicy, AccessPolicy.id == RoleAccessPolicy.access_policy_id)
                .join(RoleDefinition, RoleAccessPolicy.role_definition_id == RoleDefinition.id)
                .where(
                    and_(
                        RoleAccessPolicy.is_active == True,  # noqa: E712
                        AccessPolicy.is_active == True,  # noqa: E712
                        RoleDefinition.code.in_(role_codes),
                        or_(
                            AccessPolicy.organization_id == organization_id,
                            AccessPolicy.organization_id.is_(None),
                        ),
                    )
                )
            )
            role_policies = self.db.execute(stmt).scalars().all()
            policies.extend(role_policies)

        # Query for individual practitioner policies
        stmt = (
            select(AccessPolicy)
            .join(PractitionerAccessPolicy, AccessPolicy.id == PractitionerAccessPolicy.access_policy_id)
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

        # Filter to policies for this resource type
        filtered = []
        for policy in policies:
            rules = policy.rules
            policy_resource = rules.get("resource_type", "").lower()
            if not policy_resource or policy_resource == resource_type_lower:
                filtered.append(policy)

        return filtered

    def get_accessible_resource_ids(
        self,
        practitioner: "Practitioner",
        resource_type: str,
        organization_id: UUID,
        model_class: type,
    ) -> list[UUID]:
        """Get list of resource IDs accessible to the practitioner.

        Useful for pre-filtering or caching accessible resources.

        Args:
            practitioner: The practitioner
            resource_type: The resource type
            organization_id: The organization context
            model_class: The SQLAlchemy model class

        Returns:
            List of accessible resource UUIDs
        """
        filter_expr = self.build_sqlalchemy_filter(
            practitioner, resource_type, organization_id, model_class
        )

        stmt = select(model_class.id).where(filter_expr)
        result = self.db.execute(stmt).scalars().all()

        return list(result)
