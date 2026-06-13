# Cedar Authorization System - Quick Context

> This document provides quick context for understanding and working with the Cedar-based authorization system.

## File Locations

```
backend/sense_loop/access/cedar/
├── models.py            # DB models: AccessPolicy, RoleAccessPolicy, PractitionerAccessPolicy, BreakTheGlassAccess
├── engine.py            # CedarEngine.is_authorized() - main entry point
├── field_filter.py      # FieldFilter - removes hidden_fields from responses
├── query_filter.py      # QueryFilterBuilder - generates SQL WHERE clauses
├── break_glass.py       # BreakTheGlassManager - emergency access
├── cache.py             # PolicyCache - in-memory caching with TTL
├── policy_builder.py    # Converts DB policies to Cedar DSL
├── entity_builder.py    # Builds Cedar entities from SQLAlchemy models
├── default_policies.py  # 13 default policies, ROLE_POLICY_MAPPING

backend/sense_loop/access/policy_engine.py  # Wrapper with parallel mode support
backend/sense_loop/api/routes/break_glass.py  # BTG API endpoints

backend/tests/sense_loop/access/cedar/  # 139 unit tests
```

## Core Concepts

### Policy Structure (rules JSONB)

```python
{
    "resource_type": "patient",           # What resource type
    "actions": ["read", "update"],        # Allowed actions
    "hidden_fields": ["password_hash"],   # Remove from responses
    "readonly_fields": ["mrn"],           # Block modifications
    "conditions": {
        "same_organization": True,        # Practitioner must be in same org
        "enrollment_status": ["active"],  # Filter by status
        "resource_active": True,          # Only active resources
    },
}
```

### Authorization Flow

```
is_authorized() called
    ↓
1. Check for active BTG access → if found, ALLOW
    ↓
2. Get applicable policies:
   - From practitioner's roles (via RoleAccessPolicy)
   - From individual overrides (PractitionerAccessPolicy)
   - System-wide policies
    ↓
3. Sort by priority (higher first)
    ↓
4. For each policy:
   - Check resource_type matches
   - Check action in actions list
   - Evaluate conditions
   - If matches: apply effect (permit/forbid)
    ↓
5. If no Cedar policies found → fallback to legacy permissions
```

### Key Classes

| Class | File | Purpose |
|-------|------|---------|
| `CedarEngine` | engine.py | Main authorization, `is_authorized()`, `filter_response_fields()`, `get_query_filter()` |
| `FieldFilter` | field_filter.py | Filter hidden fields, validate readonly fields |
| `QueryFilterBuilder` | query_filter.py | Generate SQL WHERE from policies |
| `BreakTheGlassManager` | break_glass.py | Emergency access activation/revocation |
| `PolicyCache` | cache.py | TTL cache, pattern invalidation |
| `PolicyEngine` | policy_engine.py | Wrapper with parallel mode, legacy fallback |

## Common Tasks

### Check Authorization

```python
from sense_loop.access.cedar import CedarEngine

engine = CedarEngine(db)
result = engine.is_authorized(
    practitioner=user,
    action="read",  # read, create, update, delete, acknowledge, resolve, export
    resource_type="patient",  # patient, alert, care_plan, practitioner, etc.
    resource_id=uuid_or_none,
    organization_id=org_id,
)
# result.allowed, result.decision_reason, result.hidden_fields
```

### Filter Response Fields

```python
filtered = engine.filter_response_fields(
    data=patient_dict,  # or list of dicts
    practitioner=user,
    resource_type="patient",
    organization_id=org_id,
)
```

### Create Policy Override

```python
from sense_loop.access.cedar import PractitionerAccessPolicy

override = PractitionerAccessPolicy(
    practitioner_id=user_id,
    organization_id=org_id,
    access_policy_id=policy_id,
    valid_from=datetime.now(),
    valid_until=datetime.now() + timedelta(days=30),
    reason="Temporary access for project",
    granted_by_id=admin_id,
)
db.add(override)
```

### Activate BTG

```python
from sense_loop.access.cedar import BreakTheGlassManager, EmergencyType

btg = BreakTheGlassManager(db)
result = btg.activate(
    practitioner=user,
    organization_id=org_id,
    resource_type="patient",
    reason="Emergency - min 20 chars required",
    emergency_type=EmergencyType.MEDICAL_EMERGENCY,
    duration_hours=4,  # max 24
)
```

## Database Tables

| Table | Purpose |
|-------|---------|
| `sl_role_definition` | Role definitions with permission flags and `privilege_level` |
| `sl_access_policy` | Policy definitions with JSONB rules |
| `sl_role_access_policy` | Links policies to roles |
| `sl_practitioner_access_policy` | Individual overrides with time bounds |
| `sl_break_glass_access` | BTG audit records |

## Default Roles and Policies

```python
ROLE_POLICY_MAPPING = {
    "super_admin": ["patient_full_access", "alert_full_access", "clinician_management", ...],
    "doctor": ["patient_full_access", "alert_full_access", "care_plan_full_access", ...],
    "nurse": ["patient_full_access", "alert_acknowledge_only", "care_plan_full_access", ...],
    "medical_assistant": ["patient_full_access", "alert_acknowledge_only", "communication_read_only"],
}
```

## Role Privilege Levels

Each `RoleDefinition` has a `privilege_level` (int) that controls role assignment when inviting clinicians. Users can assign roles at or below their level (e.g., org_admin can create another org_admin).

| Role | Level |
|------|-------|
| `super_admin` | 100 |
| `org_admin` | 80 |
| `doctor` | 60 |
| `physician_assistant` | 55 |
| `nurse_practitioner` | 55 |
| `nurse` | 50 |
| `care_coordinator` | 45 |
| `medical_assistant` | 40 |
| `readonly` | 10 |

**API:** `GET /api/v1/sl/clinicians/roles?organization_id=<uuid>` returns roles filtered by user's level.

**Note:** `super_admin` is never assignable via invite regardless of privilege level.

## Configuration Flags

```python
# sense_loop/config.py
use_cedar_auth: bool = False       # Use Cedar as primary auth
cedar_parallel_mode: bool = True   # Run both systems, log discrepancies
cedar_cache_ttl_seconds: int = 300 # Cache TTL
```

## Testing

```bash
# Run Cedar tests (avoids testcontainers Docker issues)
pytest tests/sense_loop/access/cedar/ -v --confcutdir=tests/sense_loop/access/cedar

# Tests use mocks defined in tests/sense_loop/access/cedar/conftest.py
```

## Migration Files

- `2026_06_08_1200-b8c9d0e1f2a3_add_cedar_access_policy_tables.py` - Creates tables
- `2026_06_08_1300-c9d0e1f2a3b4_seed_cedar_default_policies.py` - Seeds default policies

## Key Patterns

### Adding a New Resource Type

1. Add policy in `default_policies.py`
2. Update `ROLE_POLICY_MAPPING`
3. Add entity builder in `entity_builder.py` if needed
4. Update tests

### Granting Temporary Access

Use `PractitionerAccessPolicy` with `valid_from`/`valid_until`:
```python
PractitionerAccessPolicy(
    practitioner_id=user.id,
    access_policy_id=policy.id,
    valid_until=datetime.now() + timedelta(days=7),
    reason="Covering for Dr. Smith",
)
```

### Emergency Access (BTG)

1. Minimum 20-char reason required
2. Max duration 24 hours
3. All access logged with `access_count`
4. Use notification hooks for supervisor alerts

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| "No matching permit policy" | No policy grants access | Check role has correct policies |
| "role in result.message" | User not in organization | Verify practitioner_roles |
| "20 characters" (BTG) | Reason too short | Provide detailed justification |
| "already exists" (BTG) | Active BTG exists | Revoke existing or wait for expiry |

## Imports

```python
# Main classes
from sense_loop.access.cedar import (
    CedarEngine,
    CedarAuthorizationResult,
    FieldFilter,
    QueryFilterBuilder,
    BreakTheGlassManager,
    EmergencyType,
    PolicyCache,
)

# Models
from sense_loop.access.cedar import (
    AccessPolicy,
    RoleAccessPolicy,
    PractitionerAccessPolicy,
    BreakTheGlassAccess,
)

# Helpers
from sense_loop.access.cedar import (
    get_policy_cache,
    get_policies_for_role,
    DEFAULT_POLICIES,
    ROLE_POLICY_MAPPING,
)
```
