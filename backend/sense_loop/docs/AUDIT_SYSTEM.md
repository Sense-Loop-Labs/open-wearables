# Audit System Documentation

## Overview

The Sense Loop audit system provides HIPAA-compliant logging of all access to Protected Health Information (PHI). It implements a tamper-evident hash chain to ensure audit log integrity and includes automated daily verification.

**Key Features:**
- Comprehensive PHI access logging
- Cryptographic hash chain for tamper detection
- Database-level immutability enforcement
- Automated daily integrity verification
- Compliance reporting endpoints

---

## 1. Audit Log Structure

### 1.1 Database Table: `sl_audit_log`

Every audit entry captures the "who, what, when, why, and outcome" of each action.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Unique identifier for the entry |
| `created_at` | TIMESTAMP | When the action occurred |
| **WHO** | | |
| `actor_type` | VARCHAR(50) | Type of actor: `practitioner`, `patient`, `system`, `api_key` |
| `actor_id` | UUID | ID of the actor |
| `actor_name` | VARCHAR(255) | Human-readable name |
| `actor_email` | VARCHAR(255) | Email address |
| `organization_id` | UUID | Organization context (FK to sl_organization) |
| **WHAT** | | |
| `action` | VARCHAR(100) | Action performed (see Action Types below) |
| `resource_type` | VARCHAR(100) | Type of resource accessed |
| `resource_id` | UUID | ID of the specific resource |
| `resource_name` | VARCHAR(255) | Human-readable resource name |
| **WHY** | | |
| `endpoint` | VARCHAR(255) | API endpoint called |
| `http_method` | VARCHAR(50) | HTTP method (GET, POST, etc.) |
| `request_id` | VARCHAR(100) | Request correlation ID |
| `ip_address` | VARCHAR(50) | Client IP address |
| `user_agent` | TEXT | Client user agent string |
| **OUTCOME** | | |
| `outcome` | VARCHAR(50) | Result: `success`, `failure`, `denied` |
| `outcome_reason` | VARCHAR(255) | Reason for failure/denial |
| **DETAILS** | | |
| `details` | JSONB | Additional context (filters, parameters) |
| `phi_fields_accessed` | JSONB | List of PHI fields accessed |
| `changes` | JSONB | For updates: `{"field": {"old": "...", "new": "..."}}` |
| **INTEGRITY** | | |
| `sequence_number` | BIGINT | Sequential counter for ordering |
| `previous_hash` | VARCHAR(255) | Hash of the previous entry |
| `entry_hash` | VARCHAR(255) | SHA-256 hash of this entry |

### 1.2 Action Types

```python
# Authentication
LOGIN = "login"
LOGOUT = "logout"
LOGIN_FAILED = "login_failed"
PASSWORD_RESET = "password_reset"
SESSION_REFRESH = "session_refresh"
SESSION_REVOKE = "session_revoke"

# CRUD Operations
CREATE = "create"
READ = "read"
UPDATE = "update"
DELETE = "delete"
LIST = "list"
VIEW = "view"

# Clinical Actions
ACKNOWLEDGE_ALERT = "acknowledge_alert"
RESOLVE_ALERT = "resolve_alert"
ESCALATE_ALERT = "escalate_alert"

# Data Actions
EXPORT = "export"
IMPORT = "import"
DOWNLOAD = "download"

# Admin Actions
INVITE = "invite"
REVOKE = "revoke"
DEACTIVATE = "deactivate"
ACTIVATE = "activate"

# Compliance
VERIFY = "verify"
INTEGRITY_CHECK_FAILED = "integrity_check_failed"
```

### 1.3 PHI Field Categories

Tracked in `phi_fields_accessed` for compliance reporting:

```python
DEMOGRAPHICS = ["first_name", "last_name", "date_of_birth", "gender", "address"]
CONTACT = ["email", "phone"]
CLINICAL = ["primary_diagnosis", "surgery_date", "medical_history"]
VITALS = ["heart_rate", "blood_pressure", "spo2", "temperature"]
IDENTIFIERS = ["mrn", "ssn", "insurance_id"]
```

---

## 2. Hash Chain Mechanism

### 2.1 How It Works

Each audit entry includes a cryptographic hash that chains to the previous entry:

```
Entry 1: hash(data₁ + GENESIS_HASH) → hash₁
Entry 2: hash(data₂ + hash₁) → hash₂
Entry 3: hash(data₃ + hash₂) → hash₃
...
```

If any entry is modified, its hash changes, breaking the chain from that point forward.

### 2.2 Hash Computation

The hash is computed from these fields:

```python
hash_data = {
    "id": str(entry_id),
    "created_at": created_at.isoformat(),
    "actor_type": actor_type,
    "actor_id": str(actor_id) if actor_id else None,
    "action": action,
    "resource_type": resource_type,
    "resource_id": str(resource_id) if resource_id else None,
    "outcome": outcome,
    "previous_hash": previous_hash,
}

# Canonical JSON + SHA-256
canonical = json.dumps(hash_data, sort_keys=True, separators=(",", ":"))
entry_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

### 2.3 Genesis Hash

The first entry in the chain uses the genesis hash:

```python
GENESIS_HASH = "0" * 64  # 64 zeros (SHA-256 produces 64 hex chars)
```

### 2.4 Verification Process

1. Load entries ordered by `sequence_number`
2. For each entry:
   - Verify `previous_hash` matches the previous entry's `entry_hash`
   - Recompute the hash from the entry's fields
   - Verify computed hash matches stored `entry_hash`
3. Detect any gaps in sequence numbers

If any check fails, the chain is broken and tampering is indicated.

---

## 3. Immutability Enforcement

### 3.1 Database Triggers

PostgreSQL triggers prevent any modification:

```sql
CREATE FUNCTION prevent_audit_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'HIPAA Compliance: Audit log entries are immutable
                     and cannot be modified or deleted. Entry ID: %', OLD.id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_prevent_update
BEFORE UPDATE ON sl_audit_log
FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();

CREATE TRIGGER audit_log_prevent_delete
BEFORE DELETE ON sl_audit_log
FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();
```

### 3.2 Protection Layers

| Layer | Protection | Scope |
|-------|------------|-------|
| Database trigger | Blocks UPDATE/DELETE | All database access |
| Hash chain | Detects modifications | Verified on demand |
| ORM restrictions | No update/delete methods | Application code |

---

## 4. Scheduled Verification

### 4.1 Celery Beat Task

A daily task verifies audit log integrity:

```python
@shared_task(name="sense_loop.verify_audit_integrity")
def verify_audit_integrity():
    """Daily task to verify audit log integrity."""
    service = AuditIntegrityService(db)
    result = service.verify_chain(limit=100000)

    if not result.is_valid:
        logger.critical(
            "AUDIT LOG INTEGRITY FAILURE: %s at sequence %d",
            result.error_message,
            result.first_invalid_sequence,
        )
        # Log the failure as an audit event
        # TODO: Send alert notification
```

### 4.2 Schedule

Configured in Celery Beat (`app/integrations/celery/core.py`):

```python
"sl-verify-audit-integrity": {
    "task": "sense_loop.verify_audit_integrity",
    "schedule": crontab(hour=5, minute=0),  # Daily at 05:00 UTC
}
```

### 4.3 Monitoring

**Log patterns to monitor:**
- `AUDIT LOG INTEGRITY FAILURE` - CRITICAL level, immediate investigation required
- `integrity_check_failed` action in audit log

**CloudWatch Alarm (recommended):**
```
Filter: "AUDIT LOG INTEGRITY FAILURE"
Threshold: >= 1 in 5 minutes
Action: SNS notification to compliance team
```

---

## 5. API Endpoints

### 5.1 Compliance Endpoints

All require `super_admin` or `org_admin` role.

**GET /api/v1/sl/compliance/audit/summary**

Returns chain statistics:
```json
{
    "total_entries": 251,
    "hashed_entries": 251,
    "unhashed_entries": 0,
    "sequence_start": 1,
    "sequence_end": 251,
    "latest_entry_at": "2026-07-04T13:45:00Z",
    "chain_coverage_percent": 100.0
}
```

**GET /api/v1/sl/compliance/audit/integrity**

Verifies chain integrity:
```json
{
    "is_valid": true,
    "entries_checked": 251,
    "first_invalid_sequence": null,
    "first_invalid_id": null,
    "error_message": null,
    "gaps_detected": null
}
```

Query parameters:
- `start_sequence` - Start verification from this sequence
- `end_sequence` - End verification at this sequence
- `limit` - Maximum entries to check (default: 10000)

**POST /api/v1/sl/compliance/audit/backfill-hashes**

Backfills hashes for entries created before hash chain was implemented:
```json
{
    "entries_updated": 248,
    "message": "Backfilled hashes for 248 entries"
}
```

Requires `super_admin` role.

### 5.2 Compliance Reports

All require `super_admin` or `org_admin` role. Each report logs its own access to the audit trail.

**GET /api/v1/sl/compliance/reports/phi-access**

PHI access report grouped by user. Shows who accessed PHI, how many times, and which fields.

Query parameters:
- `days` - Number of days to include (default: 30, max: 365)
- `organization_id` - Filter by organization (optional)

```bash
curl "http://localhost:8000/api/v1/sl/compliance/reports/phi-access?days=30" \
  -H "Authorization: Bearer $TOKEN"
```

Sample output:
```json
{
    "report_start": "2026-06-04T21:26:45.896657Z",
    "report_end": "2026-07-04T21:26:45.896657Z",
    "total_accesses": 24,
    "unique_actors": 3,
    "users": [
        {
            "actor_id": "4118c56a-b487-42c0-8386-e8af8b457c59",
            "actor_name": "Test Admin",
            "actor_email": "admin@test.com",
            "actor_type": "practitioner",
            "total_accesses": 22,
            "unique_resources": 1,
            "phi_fields": [
                "blood_pressure", "calories", "date_of_birth", "duration",
                "email", "first_name", "heart_rate", "hrv", "last_name",
                "observed_value", "patient_name", "phone", "respiratory_rate",
                "sleep_duration", "sleep_efficiency", "sleep_stages", "spo2",
                "steps", "temperature", "vital_type", "workout_type"
            ],
            "last_access_at": "2026-07-04T21:02:44.800471Z"
        },
        {
            "actor_id": "54e1998a-0998-47a0-9a92-82dcbb4a56d7",
            "actor_name": "Jane Doe",
            "actor_email": "jane.doe@email.com",
            "actor_type": "patient",
            "total_accesses": 1,
            "unique_resources": 1,
            "phi_fields": [
                "activity", "activity_restrictions", "heart_rate", "medications",
                "questionnaires", "sleep", "temperature", "vitals", "warning_signs"
            ],
            "last_access_at": "2026-07-04T20:14:49.193267Z"
        }
    ]
}
```

**GET /api/v1/sl/compliance/reports/failed-access**

Failed/denied access attempts. Useful for detecting unauthorized access patterns or brute force attacks.

Query parameters:
- `days` - Number of days to include (default: 30)
- `organization_id` - Filter by organization (optional)
- `limit` - Max entries to return (default: 100, max: 1000)

```bash
curl "http://localhost:8000/api/v1/sl/compliance/reports/failed-access?days=30" \
  -H "Authorization: Bearer $TOKEN"
```

Sample output:
```json
{
    "report_start": "2026-06-04T21:27:12.369664Z",
    "report_end": "2026-07-04T21:27:12.369664Z",
    "total_failures": 25,
    "by_reason": {
        "Invalid email or password": 24,
        "Identity verification failed": 1
    },
    "entries": [
        {
            "id": "c73a1af4-0ba8-4f77-b07b-ff38afeac7f7",
            "timestamp": "2026-06-29T22:02:21.802480Z",
            "actor_type": "unknown",
            "actor_name": null,
            "actor_email": "dmin@senseloop.health",
            "action": "login_failed",
            "resource_type": "practitioner",
            "resource_id": null,
            "outcome_reason": "Invalid email or password",
            "ip_address": null,
            "endpoint": null
        },
        {
            "id": "7b5575d8-a017-4b5b-b04a-a979ce846f3d",
            "timestamp": "2026-06-13T20:30:03.343181Z",
            "actor_type": "unknown",
            "actor_name": null,
            "actor_email": null,
            "action": "activation_failed",
            "resource_type": "patient",
            "resource_id": "a2d90eef-e3d5-41b3-83ad-59af56db7b9f",
            "outcome_reason": "Identity verification failed",
            "ip_address": null,
            "endpoint": null
        }
    ]
}
```

**GET /api/v1/sl/compliance/reports/exports**

Data export activity. Tracks PHI disclosure through exports and downloads.

Query parameters:
- `days` - Number of days to include (default: 30)
- `organization_id` - Filter by organization (optional)
- `limit` - Max entries to return (default: 100, max: 1000)

```bash
curl "http://localhost:8000/api/v1/sl/compliance/reports/exports?days=30" \
  -H "Authorization: Bearer $TOKEN"
```

Sample output (when exports exist):
```json
{
    "report_start": "2026-06-04T21:27:27.247962Z",
    "report_end": "2026-07-04T21:27:27.247962Z",
    "total_exports": 2,
    "by_resource_type": {
        "patient_vitals": 1,
        "patient_summary": 1
    },
    "entries": [
        {
            "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "timestamp": "2026-07-03T16:00:00Z",
            "actor_name": "Dr. Smith",
            "actor_email": "smith@hospital.com",
            "resource_type": "patient_vitals",
            "resource_id": "patient-uuid-here",
            "resource_name": "John Doe",
            "details": {"format": "csv", "date_range": "30d"},
            "outcome": "success"
        }
    ]
}
```

Sample output (no exports):
```json
{
    "report_start": "2026-06-04T21:27:27.247962Z",
    "report_end": "2026-07-04T21:27:27.247962Z",
    "total_exports": 0,
    "by_resource_type": {},
    "entries": []
}
```

**GET /api/v1/sl/compliance/reports/emergency-access**

Emergency/break-glass access events. These bypass normal authorization and require justification.
Should be rare - investigate any entries.

Query parameters:
- `days` - Number of days to include (default: 90)
- `organization_id` - Filter by organization (optional)

```bash
curl "http://localhost:8000/api/v1/sl/compliance/reports/emergency-access?days=90" \
  -H "Authorization: Bearer $TOKEN"
```

Sample output (when emergency access has occurred):
```json
{
    "report_start": "2026-04-05T21:27:36.912019Z",
    "report_end": "2026-07-04T21:27:36.912019Z",
    "total_emergency_accesses": 1,
    "entries": [
        {
            "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "timestamp": "2026-06-15T03:30:00Z",
            "actor_name": "Dr. Emergency",
            "actor_email": "emergency@hospital.com",
            "action": "emergency_access",
            "resource_type": "patient",
            "resource_id": "patient-uuid-here",
            "resource_name": "Jane Doe",
            "reason": "Patient unresponsive, needed history",
            "details": {"justification": "Emergency room admission"}
        }
    ]
}
```

Sample output (no emergency accesses - expected normal state):
```json
{
    "report_start": "2026-04-05T21:27:36.912019Z",
    "report_end": "2026-07-04T21:27:36.912019Z",
    "total_emergency_accesses": 0,
    "entries": []
}
```

---

## 6. Usage Examples

### 6.1 Logging PHI Access

```python
from sense_loop.audit import AuditLogger, get_audit_context

# In a route handler
ctx = get_audit_context()
ctx.set_practitioner(practitioner)
ctx.organization_id = patient.organization_id

audit = AuditLogger(db)
audit.log_access(
    resource_type="patient_vitals",
    resource_id=patient.id,
    resource_name=patient.full_name,
    phi_fields_accessed=["heart_rate", "blood_pressure", "temperature"],
)
db.commit()  # Required for read-only endpoints
```

### 6.2 Logging Updates with Changes

```python
audit.log_update(
    resource_type="patient_task",
    resource_id=task.id,
    resource_name=task.title,
    changes={"status": {"old": "pending", "new": "completed"}},
)
```

### 6.3 Logging Access Denials

```python
audit.log_denied(
    action="read",
    resource_type="patient",
    resource_id=patient_id,
    reason="User not authorized for this organization",
)
```

### 6.4 Mobile/Patient Context

```python
from sense_loop.audit.context import AuditContext

audit_ctx = AuditContext(
    actor_type="patient",
    actor_id=patient.id,
    actor_name=patient.full_name,
    actor_email=patient.email,
    organization_id=patient.organization_id,
    endpoint="/api/v1/sl/data/summary",
    http_method="POST",
)
audit = AuditLogger(db, audit_ctx)
```

---

## 7. Verification Commands

### 7.1 Manual Verification (Python)

```python
from app.database import SessionLocal
from sense_loop.audit import AuditIntegrityService

db = SessionLocal()
service = AuditIntegrityService(db)

# Get summary
print(service.get_chain_summary())

# Verify chain
result = service.verify_chain()
print(f"Valid: {result.is_valid}, Entries: {result.entries_checked}")

db.close()
```

### 7.2 Via API (curl)

```bash
# Get summary
curl http://localhost:8000/api/v1/sl/compliance/audit/summary \
  -H "Authorization: Bearer $TOKEN"

# Verify integrity
curl http://localhost:8000/api/v1/sl/compliance/audit/integrity \
  -H "Authorization: Bearer $TOKEN"

# Backfill hashes (super_admin only)
curl -X POST http://localhost:8000/api/v1/sl/compliance/audit/backfill-hashes \
  -H "Authorization: Bearer $TOKEN"
```

---

## 8. Migration History

| Migration | Description |
|-----------|-------------|
| `8757d2c0eb1e` | Add `entry_hash`, `previous_hash`, `sequence_number` columns |
| `b93071aba2c0` | Add immutability triggers (prevent UPDATE/DELETE) |

---

## 9. Files Reference

| File | Purpose |
|------|---------|
| `sense_loop/models/audit_log.py` | AuditLog model, action constants, PHI categories |
| `sense_loop/audit/logger.py` | AuditLogger class for creating entries |
| `sense_loop/audit/context.py` | AuditContext for request-scoped actor info |
| `sense_loop/audit/integrity.py` | Hash computation and verification service |
| `sense_loop/audit/middleware.py` | Auto-captures request context, logs 403s |
| `sense_loop/api/routes/compliance.py` | API endpoints for verification |
| `app/integrations/celery/tasks/sense_loop_tasks.py` | Scheduled verification task |

---

## 10. HIPAA Compliance Notes

This audit system addresses HIPAA Technical Safeguard § 164.312(b) - Audit Controls:

1. **Activity Recording**: All PHI access is logged with actor, resource, timestamp, and outcome
2. **Tamper Evidence**: Hash chain detects any modifications to audit records
3. **Immutability**: Database triggers prevent deletion or modification
4. **Regular Review**: Daily automated verification with alerting
5. **Retention**: Audit logs should be retained for 6 years (configure via log retention settings)

**Recommendations for Production:**
- Set up CloudWatch alarms for integrity failures
- Use separate database user with limited privileges for the application
- Export hash chain snapshots to S3 with Object Lock for external verification
- Review audit logs regularly as part of compliance program
