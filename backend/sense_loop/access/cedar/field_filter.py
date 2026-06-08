"""Filter response fields based on Cedar policies.

This module provides field-level access control, removing or masking
fields that the practitioner should not see based on their policies.
"""

from __future__ import annotations

import copy
import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .models import AccessPolicy, PractitionerAccessPolicy, RoleAccessPolicy
from .policy_builder import get_hidden_fields_from_policy, get_readonly_fields_from_policy

if TYPE_CHECKING:
    from sense_loop.models import Practitioner

logger = logging.getLogger(__name__)


class FieldFilter:
    """Filters response fields based on Cedar policies.

    Removes hidden fields and marks readonly fields based on the
    applicable policies for a practitioner and resource type.
    """

    # Default sensitive fields that should always be hidden unless explicitly permitted
    DEFAULT_HIDDEN_FIELDS = {
        "patient": ["password_hash"],
        "practitioner": ["password_hash", "password_reset_token"],
    }

    # Mask value for hidden fields (if masking instead of removing)
    MASK_VALUE = "***REDACTED***"

    def __init__(self, db: Session):
        """Initialize the field filter.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self._cache: dict[str, tuple[set[str], set[str]]] = {}

    def filter_fields(
        self,
        data: dict | list,
        practitioner: "Practitioner",
        resource_type: str,
        organization_id: UUID,
        mask_hidden: bool = False,
    ) -> dict | list:
        """Filter fields from response data based on policies.

        Args:
            data: Response data (dict or list of dicts)
            practitioner: The practitioner requesting the data
            resource_type: The type of resource
            organization_id: The organization context
            mask_hidden: If True, mask hidden fields instead of removing them

        Returns:
            Filtered data with hidden fields removed or masked
        """
        hidden_fields, readonly_fields = self._get_field_restrictions(
            practitioner, resource_type, organization_id
        )

        # Add default hidden fields for this resource type
        default_hidden = self.DEFAULT_HIDDEN_FIELDS.get(resource_type.lower(), [])
        hidden_fields = hidden_fields | set(default_hidden)

        if isinstance(data, list):
            return [
                self._filter_dict(item, hidden_fields, readonly_fields, mask_hidden)
                for item in data
            ]
        elif isinstance(data, dict):
            return self._filter_dict(data, hidden_fields, readonly_fields, mask_hidden)
        else:
            return data

    def _filter_dict(
        self,
        data: dict,
        hidden_fields: set[str],
        readonly_fields: set[str],
        mask_hidden: bool,
    ) -> dict:
        """Filter a single dictionary.

        Args:
            data: Dictionary to filter
            hidden_fields: Set of field names to hide
            readonly_fields: Set of field names that are readonly
            mask_hidden: If True, mask hidden fields instead of removing

        Returns:
            Filtered dictionary
        """
        if not data:
            return data

        # Make a copy to avoid modifying the original
        result = copy.copy(data)

        for field in hidden_fields:
            if field in result:
                if mask_hidden:
                    result[field] = self.MASK_VALUE
                else:
                    del result[field]

        # Handle nested dictionaries
        for key, value in list(result.items()):
            if isinstance(value, dict):
                # Recursively filter nested dicts
                result[key] = self._filter_nested(
                    value, hidden_fields, readonly_fields, mask_hidden, prefix=key
                )
            elif isinstance(value, list):
                # Filter list items if they're dicts
                result[key] = [
                    self._filter_nested(
                        item, hidden_fields, readonly_fields, mask_hidden, prefix=key
                    )
                    if isinstance(item, dict)
                    else item
                    for item in value
                ]

        return result

    def _filter_nested(
        self,
        data: dict,
        hidden_fields: set[str],
        readonly_fields: set[str],
        mask_hidden: bool,
        prefix: str,
    ) -> dict:
        """Filter nested dictionary fields.

        Hidden fields can be specified as:
        - Simple: "ssn" (matches at any level)
        - Dotted: "patient.ssn" (matches specific nested path)

        Args:
            data: Nested dictionary to filter
            hidden_fields: Set of field names to hide
            readonly_fields: Set of readonly field names
            mask_hidden: If True, mask instead of remove
            prefix: Current path prefix

        Returns:
            Filtered dictionary
        """
        if not data:
            return data

        result = copy.copy(data)

        for key, value in list(result.items()):
            full_key = f"{prefix}.{key}"

            # Check if this field should be hidden
            if key in hidden_fields or full_key in hidden_fields:
                if mask_hidden:
                    result[key] = self.MASK_VALUE
                else:
                    del result[key]
            elif isinstance(value, dict):
                result[key] = self._filter_nested(
                    value, hidden_fields, readonly_fields, mask_hidden, full_key
                )
            elif isinstance(value, list):
                result[key] = [
                    self._filter_nested(
                        item, hidden_fields, readonly_fields, mask_hidden, full_key
                    )
                    if isinstance(item, dict)
                    else item
                    for item in value
                ]

        return result

    def _get_field_restrictions(
        self,
        practitioner: "Practitioner",
        resource_type: str,
        organization_id: UUID,
    ) -> tuple[set[str], set[str]]:
        """Get field restrictions for a practitioner and resource type.

        Args:
            practitioner: The practitioner
            resource_type: The resource type
            organization_id: The organization context

        Returns:
            Tuple of (hidden_fields, readonly_fields) sets
        """
        cache_key = f"{practitioner.id}:{resource_type}:{organization_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        hidden_fields: set[str] = set()
        readonly_fields: set[str] = set()

        # Get applicable policies
        policies = self._get_applicable_policies(
            practitioner, resource_type, organization_id
        )

        for policy in policies:
            if not policy.is_active:
                continue

            hidden_fields.update(get_hidden_fields_from_policy(policy))
            readonly_fields.update(get_readonly_fields_from_policy(policy))

        self._cache[cache_key] = (hidden_fields, readonly_fields)
        return hidden_fields, readonly_fields

    def _get_applicable_policies(
        self,
        practitioner: "Practitioner",
        resource_type: str,
        organization_id: UUID,
    ) -> list[AccessPolicy]:
        """Get applicable policies for field filtering.

        Args:
            practitioner: The practitioner
            resource_type: The resource type
            organization_id: The organization context

        Returns:
            List of applicable AccessPolicy records
        """
        from datetime import datetime

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

    def get_readonly_fields(
        self,
        practitioner: "Practitioner",
        resource_type: str,
        organization_id: UUID,
    ) -> set[str]:
        """Get the set of readonly fields for a practitioner.

        Useful for validation - these fields cannot be modified.

        Args:
            practitioner: The practitioner
            resource_type: The resource type
            organization_id: The organization context

        Returns:
            Set of readonly field names
        """
        _, readonly_fields = self._get_field_restrictions(
            practitioner, resource_type, organization_id
        )
        return readonly_fields

    def validate_update(
        self,
        update_data: dict,
        practitioner: "Practitioner",
        resource_type: str,
        organization_id: UUID,
    ) -> list[str]:
        """Validate that an update doesn't modify readonly fields.

        Args:
            update_data: Dictionary of fields being updated
            practitioner: The practitioner making the update
            resource_type: The resource type
            organization_id: The organization context

        Returns:
            List of error messages for any readonly field violations
        """
        readonly_fields = self.get_readonly_fields(
            practitioner, resource_type, organization_id
        )

        violations = []
        for field in update_data.keys():
            if field in readonly_fields:
                violations.append(f"Field '{field}' is readonly and cannot be modified")

        return violations

    def clear_cache(self) -> None:
        """Clear the field restrictions cache."""
        self._cache.clear()
