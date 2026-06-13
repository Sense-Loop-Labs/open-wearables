# Cedar-Based Authorization System

## Overview

The Cedar authorization system provides fine-grained access control for the Sense Loop clinical platform. It replaces the previous 10 boolean permission flags with a flexible policy-based system supporting:

- **Field-level access control** - Hide or make fields read-only per policy
- **Role-based policies** - Assign policies to roles (doctor, nurse, etc.)
- **Individual overrides** - Grant specific practitioners additional permissions
- **Time-bounded access** - Temporary access grants with automatic expiration
- **Break-the-glass emergency access** - Audited emergency access for critical situations
- **Query-time filtering** - Efficiently filter list endpoints based on policies

## Architecture

```
sense_loop/access/cedar/
├── __init__.py           # Public API exports
├── models.py             # SQLAlchemy models (AccessPolicy, etc.)
├── engine.py             # CedarEngine - main authorization class
├── policy_builder.py     # Generate Cedar DSL from DB records
├── entity_builder.py     # Build Cedar entities from models
├── field_filter.py       # Filter response fields (hidden/readonly)
├── query_filter.py       # Generate SQL WHERE clauses
├── break_glass.py        # Emergency access management
├── cache.py              # In-memory caching with TTL
└── default_policies.py   # Default policies matching legacy permissions
```

## Quick Start

### Basic Authorization Check

```python
from sense_loop.access.cedar import CedarEngine

# Create engine with database session
engine = CedarEngine(db)

# Check if practitioner can read a patient
result = engine.is_authorized(
    practitioner=current_user,
    action="read",
    resource_type="patient",
    resource_id=patient.id,
    organization_id=org_id,
)

if result.allowed:
    # Access granted
    patient_data = get_patient(patient_id)

    # Filter out hidden fields before returning
    filtered_data = engine.filter_response_fields(
        data=patient_data,
        practitioner=current_user,
        resource_type="patient",
        organization_id=org_id,
    )
    return filtered_data
else:
    raise HTTPException(403, result.decision_reason)
```

### Using the PolicyEngine Wrapper (Recommended)

The `PolicyEngine` class provides a higher-level interface with parallel mode support:

```python
from sense_loop.access import PolicyEngine

policy_engine = PolicyEngine(db)

# Check authorization with automatic legacy fallback
result = policy_engine.is_authorized_with_parallel_check(
    practitioner=current_user,
    action="update",
    resource_type="patient",
    resource_id=patient_id,
    organization_id=org_id,
)

if not result.allowed:
    raise HTTPException(403, "Access denied")
```

## Database Models

### AccessPolicy

Stores policy definitions with JSON rules:

```python
class AccessPolicy(Base):
    __tablename__ = "sl_access_policy"

    id: UUID
    code: str               # Unique identifier, e.g., "patient_full_access"
    name: str               # Human-readable name
    description: str | None
    organization_id: UUID | None  # None = system-wide policy
    rules: dict             # JSONB - see schema below
    effect: str             # "permit" or "forbid"
    priority: int           # Higher = evaluated first (default: 100)
    is_active: bool
    is_system_policy: bool  # System policies can't be deleted
```

#### Rules Schema

```json
{
  "resource_type": "patient",
  "actions": ["read", "update"],
  "hidden_fields": ["password_hash", "ssn"],
  "readonly_fields": ["mrn", "date_of_birth"],
  "conditions": {
    "same_organization": true,
    "enrollment_status": ["active", "enrolled"],
    "resource_active": true,
    "resource_attrs": {
      "severity": "critical"
    }
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `resource_type` | string | Resource this policy applies to (patient, alert, etc.) |
| `actions` | string[] | Allowed actions (read, create, update, delete, acknowledge, resolve, export) |
| `hidden_fields` | string[] | Fields to remove from responses |
| `readonly_fields` | string[] | Fields that cannot be modified |
| `conditions.same_organization` | bool | Require practitioner and resource in same org |
| `conditions.enrollment_status` | string[] | Allowed enrollment statuses |
| `conditions.resource_active` | bool | Require resource.is_active = true |
| `conditions.resource_attrs` | object | Custom attribute conditions |

### RoleAccessPolicy

Links policies to roles:

```python
class RoleAccessPolicy(Base):
    __tablename__ = "sl_role_access_policy"

    id: UUID
    role_definition_id: UUID  # FK to sl_role_definition
    access_policy_id: UUID    # FK to sl_access_policy
    priority_override: int | None  # Override policy priority for this role
    is_active: bool
```

### PractitionerAccessPolicy

Individual practitioner overrides with time bounds:

```python
class PractitionerAccessPolicy(Base):
    __tablename__ = "sl_practitioner_access_policy"

    id: UUID
    practitioner_id: UUID
    organization_id: UUID
    access_policy_id: UUID
    valid_from: datetime | None   # Start of access window
    valid_until: datetime | None  # End of access window
    reason: str | None            # Why override was granted
    granted_by_id: UUID | None    # Who granted the override
```

### BreakTheGlassAccess

Emergency access records:

```python
class BreakTheGlassAccess(Base):
    __tablename__ = "sl_break_glass_access"

    id: UUID
    practitioner_id: UUID
    organization_id: UUID
    resource_type: str
    resource_id: UUID | None  # None = type-level access
    reason: str               # Required justification (min 20 chars)
    emergency_type: str       # medical_emergency, system_outage, etc.
    activated_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    revoked_by_id: UUID | None
    revocation_reason: str | None
    access_count: int         # How many times access was used
```

## Policy Evaluation

### Evaluation Order

1. **Break-the-glass check** - If active BTG access exists, immediately allow
2. **Collect applicable policies** - From roles, individual overrides, and system policies
3. **Sort by priority** - Higher priority evaluated first
4. **Match conditions** - Check resource type, action, and conditions
5. **Apply effect** - First matching `forbid` denies; `permit` allows
6. **Legacy fallback** - If no Cedar policies, check old permission flags

### CedarAuthorizationResult

```python
@dataclass
class CedarAuthorizationResult:
    allowed: bool                    # Whether access is granted
    decision_reason: str             # Human-readable explanation
    matched_policies: list[str]      # Policy codes that matched
    hidden_fields: list[str]         # Fields to hide from response
    readonly_fields: list[str]       # Fields that can't be modified
    btg_access: bool                 # Whether BTG was used
    btg_access_id: UUID | None       # BTG record ID if applicable
```

## Field Filtering

### Hiding Fields

Fields listed in `hidden_fields` are removed from API responses:

```python
# Policy defines hidden_fields: ["password_hash", "ssn"]

original_data = {
    "id": "123",
    "name": "John Doe",
    "ssn": "123-45-6789",
    "password_hash": "abc123"
}

filtered = engine.filter_response_fields(data, practitioner, "patient", org_id)
# Result: {"id": "123", "name": "John Doe"}
```

### Masking Instead of Removing

```python
filter = FieldFilter(db)
filtered = filter.filter_fields(
    data=original_data,
    practitioner=practitioner,
    resource_type="patient",
    organization_id=org_id,
    mask_hidden=True  # Replace with "***REDACTED***" instead of removing
)
```

### Validating Updates

Check for readonly field violations before saving:

```python
filter = FieldFilter(db)
violations = filter.validate_update(
    update_data={"mrn": "NEW_MRN", "name": "New Name"},
    practitioner=practitioner,
    resource_type="patient",
    organization_id=org_id,
)

if violations:
    raise HTTPException(400, f"Cannot modify readonly fields: {violations}")
```

## Query Filtering

Generate SQL WHERE clauses for list endpoints:

```python
builder = QueryFilterBuilder(db)

# Get SQL WHERE clause
where_clause = builder.build_filter(
    practitioner=current_user,
    resource_type="patient",
    organization_id=org_id,
)
# Returns: "organization_id = 'uuid' AND (enrollment_status IN ('active', 'enrolled'))"

# Or get SQLAlchemy filter expression
filter_expr = builder.build_sqlalchemy_filter(
    practitioner=current_user,
    resource_type="patient",
    organization_id=org_id,
    model_class=Patient,
)

patients = db.query(Patient).filter(filter_expr).all()
```

## Break-the-Glass Access

### Activation

```python
from sense_loop.access.cedar import BreakTheGlassManager, EmergencyType

btg = BreakTheGlassManager(db)

result = btg.activate(
    practitioner=current_user,
    organization_id=org_id,
    resource_type="patient",
    resource_id=specific_patient_id,  # Optional - None for all patients
    reason="Patient arrived unconscious, need immediate access to medical history",
    emergency_type=EmergencyType.MEDICAL_EMERGENCY,
    duration_hours=4,  # Optional, default 4, max 24
)

if result.success:
    print(f"BTG access granted until {result.expires_at}")
    print(f"BTG ID: {result.btg_access_id}")
```

### Revocation

```python
result = btg.revoke(
    btg_access_id=btg_id,
    revoked_by=admin_user,
    reason="Emergency resolved",
)

if result.success:
    print(f"Revoked. Access was used {result.access_count} times.")
```

### Notification Hooks

Register callbacks for BTG events:

```python
def notify_supervisor(event: str, btg_access, practitioner):
    if event == "btg_activated":
        send_alert_to_supervisors(
            f"{practitioner.email} activated BTG access",
            btg_access.reason
        )

btg.register_notification_hook(notify_supervisor)
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/break-glass/activate` | POST | Activate BTG access |
| `/api/break-glass/{id}/revoke` | POST | Revoke BTG access |
| `/api/break-glass/active` | GET | List active BTG for current user |
| `/api/break-glass/history` | GET | BTG history for organization |

## Caching

### Policy Cache

In-memory cache with TTL to reduce database load:

```python
from sense_loop.access.cedar import PolicyCache, get_policy_cache

# Get global cache instance
cache = get_policy_cache()

# Manual cache operations
cache.set("key", value, ttl_seconds=300)
cached = cache.get("key")

# Invalidation
cache.invalidate_for_practitioner(practitioner_id)
cache.invalidate_for_organization(org_id)
cache.invalidate_by_pattern("practitioner:*:patient")
cache.clear()  # Clear entire cache

# Statistics
stats = cache.stats()
print(f"Hit rate: {stats['hit_rate']:.2%}")
```

### Cache Configuration

```python
# In sense_loop/config.py
use_cedar_auth: bool = False           # Enable Cedar authorization
cedar_parallel_mode: bool = True       # Run both old and new systems
cedar_cache_ttl_seconds: int = 300     # Cache TTL (5 minutes)
```

## Default Policies

The system includes default policies matching the legacy permission flags:

| Policy Code | Description |
|-------------|-------------|
| `patient_full_access` | Read/write patient records |
| `patient_read_only` | Read-only patient access |
| `alert_full_access` | Full alert management |
| `alert_acknowledge_only` | Acknowledge but not resolve |
| `alert_resolve` | Resolve alerts |
| `care_plan_full_access` | Full care plan access |
| `clinician_management` | Manage practitioners |
| `org_settings_management` | Update org settings |
| `audit_log_access` | View audit logs |
| `alert_protocol_management` | Manage alert protocols |
| `data_export` | Export data |
| `communication_read_only` | Read messages only |
| `communication_full_access` | Send messages |

### Role Mappings

```python
ROLE_POLICY_MAPPING = {
    "super_admin": ["patient_full_access", "alert_full_access", ...],
    "doctor": ["patient_full_access", "alert_full_access", "care_plan_full_access", ...],
    "nurse": ["patient_full_access", "alert_acknowledge_only", "care_plan_full_access", ...],
    "medical_assistant": ["patient_full_access", "alert_acknowledge_only", "communication_read_only"],
    # ...
}
```

## Migration Guide

### Phase 1: Parallel Mode (Current)

Both old and new authorization systems run simultaneously:

```python
# config.py
use_cedar_auth = False       # Cedar not primary yet
cedar_parallel_mode = True   # Log discrepancies
```

Check logs for `"Policy decision mismatch"` entries.

### Phase 2: Enable Cedar

```python
use_cedar_auth = True
cedar_parallel_mode = True   # Keep logging for safety
```

### Phase 3: Disable Legacy

```python
use_cedar_auth = True
cedar_parallel_mode = False  # Stop legacy checks
```

## Creating Custom Policies

### Via Database

```python
from sense_loop.access.cedar import AccessPolicy

policy = AccessPolicy(
    code="custom_limited_patient_access",
    name="Limited Patient Access",
    description="Access only to active patients with specific conditions",
    organization_id=org_id,  # Org-specific policy
    rules={
        "resource_type": "patient",
        "actions": ["read"],
        "hidden_fields": ["ssn", "insurance_info"],
        "readonly_fields": ["mrn"],
        "conditions": {
            "same_organization": True,
            "enrollment_status": ["active"],
            "resource_active": True,
        },
    },
    effect="permit",
    priority=75,
    is_active=True,
    is_system_policy=False,
)
db.add(policy)
db.commit()
```

### Assigning to Role

```python
from sense_loop.access.cedar import RoleAccessPolicy

role_policy = RoleAccessPolicy(
    role_definition_id=nurse_role.id,
    access_policy_id=policy.id,
    is_active=True,
)
db.add(role_policy)
```

### Individual Override

```python
from sense_loop.access.cedar import PractitionerAccessPolicy

# Grant a medical assistant messaging permissions for 30 days
override = PractitionerAccessPolicy(
    practitioner_id=ma_user.id,
    organization_id=org_id,
    access_policy_id=communication_full_access_policy.id,
    valid_from=datetime.now(),
    valid_until=datetime.now() + timedelta(days=30),
    reason="Cross-trained for triage support per Dr. Johnson",
    granted_by_id=admin_user.id,
)
db.add(override)
```

## Testing

Run Cedar-specific tests:

```bash
# All Cedar tests
pytest tests/sense_loop/access/cedar/ -v --confcutdir=tests/sense_loop/access/cedar

# Specific module
pytest tests/sense_loop/access/cedar/test_engine.py -v
```

## Troubleshooting

### Access Denied Unexpectedly

1. Check `result.decision_reason` for explanation
2. Verify practitioner has role in the organization
3. Check if policies are active (`is_active=True`)
4. Verify policy conditions match resource state
5. Check for higher-priority `forbid` policies

### BTG Not Working

1. Reason must be at least 20 characters
2. Practitioner must have a role in the organization
3. Check if BTG already active (can't stack)
4. Verify BTG hasn't expired

### Cache Issues

```python
# Clear cache after policy changes
engine.invalidate_cache(organization_id=org_id)

# Or clear all
get_policy_cache().clear()
```

## Security Considerations

1. **All BTG access is logged** - Access count tracked, supervisor notifications
2. **BTG requires justification** - Minimum 20 character reason required
3. **BTG is time-limited** - Maximum 24 hours, configurable per activation
4. **Policy changes are audited** - Track who created/modified policies
5. **Parallel mode catches regressions** - Log when old/new systems disagree
6. **Hidden fields are always filtered** - Can't bypass via API manipulation
7. **Role assignment uses privilege levels** - Prevents privilege escalation when inviting clinicians

## Role Privilege Levels

### Overview

Each `RoleDefinition` has a `privilege_level` field (integer) that controls which roles a user can assign when inviting new clinicians. This prevents privilege escalation - users can only assign roles at or below their own level.

### Default Privilege Levels

| Role | Privilege Level | Description |
|------|-----------------|-------------|
| `super_admin` | 100 | System-wide admin, can assign any role |
| `org_admin` | 80 | Organization admin, can assign all clinical roles |
| `doctor` | 60 | Physician |
| `physician_assistant` | 55 | PA |
| `nurse_practitioner` | 55 | NP |
| `nurse` | 50 | Nurse |
| `care_coordinator` | 45 | Care coordinator |
| `medical_assistant` | 40 | Medical assistant |
| `readonly` | 10 | Read-only access |

### How It Works

When a user with `can_manage_clinicians` permission invites a new clinician:

1. The system determines the user's highest privilege level in the organization
2. The `/api/v1/sl/clinicians/roles` endpoint returns only roles where:
   - `privilege_level <= user's highest level`
   - `code != 'super_admin'` (never assignable via invite)
   - Role is active
   - Role is system-wide OR belongs to the organization

### Example

An `org_admin` (level 80) can assign:
- `org_admin` (80) - same level is allowed
- `doctor` (60), `nurse` (50), `medical_assistant` (40), etc.

An `org_admin` **cannot** assign:
- `super_admin` (100) - explicitly excluded from invites

### API Endpoint

```
GET /api/v1/sl/clinicians/roles?organization_id=<uuid>
```

Returns `RoleDefinition[]` filtered by the current user's privilege level.

### Custom Roles

Organizations can create custom roles with any privilege level. When creating custom roles:
- Set `privilege_level` appropriately based on the role's permissions
- Higher levels = more privileged roles
- Consider which existing roles should be able to assign the custom role

### Database

```sql
-- Check privilege levels
SELECT code, display_name, privilege_level
FROM sl_role_definition
ORDER BY privilege_level DESC;
```

### Relationship to Cedar

Privilege levels are **complementary** to Cedar policies:

- **Cedar** answers: "Can this user perform this action?" (e.g., can they invite clinicians?)
- **Privilege level** answers: "Which roles can they assign?" (data constraint, not authorization)

This separation keeps the authorization logic clean while preventing privilege escalation through a simple, auditable mechanism.
