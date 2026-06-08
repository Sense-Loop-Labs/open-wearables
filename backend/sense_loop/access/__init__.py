"""RBAC access control system with Cedar-based fine-grained authorization."""

from .permissions import Permission
from .policy_engine import (
    CurrentPractitioner,
    PolicyEngine,
    get_current_practitioner,
    require_permission,
)

# Cedar-based authorization (optional, controlled by config)
from .cedar import (
    CedarEngine,
    CedarAuthorizationResult,
    AccessPolicy,
    RoleAccessPolicy,
    PractitionerAccessPolicy,
    BreakTheGlassAccess,
    BreakTheGlassManager,
    FieldFilter,
    QueryFilterBuilder,
    PolicyCache,
    get_policy_cache,
)

__all__ = [
    # Legacy RBAC
    "CurrentPractitioner",
    "Permission",
    "PolicyEngine",
    "get_current_practitioner",
    "require_permission",
    # Cedar authorization
    "CedarEngine",
    "CedarAuthorizationResult",
    "AccessPolicy",
    "RoleAccessPolicy",
    "PractitionerAccessPolicy",
    "BreakTheGlassAccess",
    "BreakTheGlassManager",
    "FieldFilter",
    "QueryFilterBuilder",
    "PolicyCache",
    "get_policy_cache",
]
