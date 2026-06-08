"""Cedar-based authorization system for fine-grained access control.

This module provides a flexible policy-based authorization system using
Cedar policy language, supporting:
- Field-level access control (hidden/readonly fields)
- Role-based policy assignment
- Individual practitioner overrides with time bounds
- Break-the-glass emergency access with audit
- Query-time filtering for list endpoints

Usage:
    from sense_loop.access.cedar import CedarEngine, CedarAuthorizationResult

    engine = CedarEngine(db)
    result = engine.is_authorized(
        practitioner=current_user,
        action="read",
        resource_type="patient",
        resource_id=patient.id,
        organization_id=org_id,
    )

    if result.allowed:
        # Filter response fields
        response = engine.filter_response_fields(
            data=patient_dict,
            practitioner=current_user,
            resource_type="patient",
            organization_id=org_id,
        )
"""

from .engine import CedarAuthorizationResult, CedarEngine
from .entity_builder import (
    CedarEntity,
    build_entities_for_authorization,
    build_patient_entity,
    build_practitioner_entity,
    build_resource_entity,
    make_entity_uid,
)
from .models import (
    AccessPolicy,
    BreakTheGlassAccess,
    PractitionerAccessPolicy,
    RoleAccessPolicy,
)
from .policy_builder import (
    build_cedar_policy,
    build_cedar_schema,
    build_policies_from_db,
    get_hidden_fields_from_policy,
    get_readonly_fields_from_policy,
)
from .field_filter import FieldFilter
from .query_filter import QueryFilterBuilder
from .cache import (
    CachedCedarEngine,
    PolicyCache,
    get_policy_cache,
    make_cache_key,
    make_field_filter_cache_key,
)
from .break_glass import (
    BreakTheGlassManager,
    BTGActivationResult,
    BTGRevocationResult,
    EmergencyType,
)
from .default_policies import (
    DEFAULT_POLICIES,
    ROLE_POLICY_MAPPING,
    get_policies_for_role,
    get_policy_by_code,
)

__all__ = [
    # Engine
    "CedarEngine",
    "CedarAuthorizationResult",
    # Models
    "AccessPolicy",
    "RoleAccessPolicy",
    "PractitionerAccessPolicy",
    "BreakTheGlassAccess",
    # Entity building
    "CedarEntity",
    "make_entity_uid",
    "build_practitioner_entity",
    "build_patient_entity",
    "build_resource_entity",
    "build_entities_for_authorization",
    # Policy building
    "build_cedar_policy",
    "build_cedar_schema",
    "build_policies_from_db",
    "get_hidden_fields_from_policy",
    "get_readonly_fields_from_policy",
    # Field and query filtering
    "FieldFilter",
    "QueryFilterBuilder",
    # Caching
    "CachedCedarEngine",
    "PolicyCache",
    "get_policy_cache",
    "make_cache_key",
    "make_field_filter_cache_key",
    # Break-the-glass
    "BreakTheGlassManager",
    "BTGActivationResult",
    "BTGRevocationResult",
    "EmergencyType",
    # Default policies
    "DEFAULT_POLICIES",
    "ROLE_POLICY_MAPPING",
    "get_policies_for_role",
    "get_policy_by_code",
]
