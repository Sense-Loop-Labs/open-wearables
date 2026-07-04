# Audit Controls Remediation Plan

**Related To:** HIPAA Technical Safeguards § 164.312(b)
**Created:** July 4, 2026
**Priority:** Critical - Must complete before production PHI handling

---

## Executive Summary

The current audit logging implementation provides a solid foundation but has significant gaps that must be addressed for HIPAA compliance. This document details the missing audit controls and provides a remediation plan.

**Current State:**
- 10 of 16 route files have audit logging
- Log retention is 30 days (requires 6 years)
- No audit logging for mobile API (patient self-service)
- No audit logging for dashboard (aggregate PHI views)

---

## 1. Routes Missing Audit Logging

### 1.1 CRITICAL: `mobile.py` - Patient Mobile API

**File:** `backend/sense_loop/api/routes/mobile.py`
**Endpoints:** 14+
**PHI Exposure:** HIGH

| Endpoint | Method | PHI Fields | Action Required |
|----------|--------|------------|-----------------|
| `/summary` | POST | vitals, heart_rate, temperature, blood_pressure, weight, sleep, HRV | Log PHI_VIEW |
| `/care-plan` | POST | medications, activity_restrictions, warning_signs, questionnaires | Log PHI_VIEW |
| `/questionnaire/submit` | POST | questionnaire answers (clinical data) | Log PHI_CREATE |
| `/tasks` | GET | task details, instructions | Log PHI_VIEW |
| `/tasks/pending` | GET | pending tasks | Log PHI_VIEW |
| `/tasks/{id}/complete` | POST | task completion | Log PHI_UPDATE |
| `/tasks/{id}/skip` | POST | task skip with reason | Log PHI_UPDATE |
| `/tasks/{id}/snooze` | POST | task snooze | Log PHI_UPDATE |
| `/tasks/{id}/confirm` | POST | task confirmation | Log PHI_UPDATE |
| `/instruction-plans` | GET | care plan details | Log PHI_VIEW |
| `/instruction-plans/{id}/content` | GET | full plan content | Log PHI_VIEW |
| `/devices/register` | POST | device info | Log DEVICE_REGISTER |
| `/devices/unregister` | POST | device info | Log DEVICE_UNREGISTER |
| `/devices/test-push` | POST | - | Log TEST_NOTIFICATION |

**Implementation Notes:**
- Actor type should be `patient` (not `practitioner`)
- Must extract patient ID from JWT token for actor_id
- Consider lower verbosity for high-frequency endpoints (summary)

### 1.2 CRITICAL: `dashboard.py` - Clinician Dashboard

**File:** `backend/sense_loop/api/routes/dashboard.py`
**Endpoints:** 4
**PHI Exposure:** HIGH

| Endpoint | Method | PHI Fields | Action Required |
|----------|--------|------------|-----------------|
| `/overview` | GET | patient counts (aggregate) | Log DASHBOARD_VIEW |
| `/critical-patients` | GET | patient names, MRNs, status | Log PHI_VIEW with patient IDs |
| `/recent-alerts` | GET | patient names, vital values | Log PHI_VIEW with alert IDs |
| `/alerts-by-day` | GET | aggregate counts | Log DASHBOARD_VIEW |

**Implementation Notes:**
- Log IDs of all patients/alerts returned in response
- Track `phi_fields_accessed: ["full_name", "mrn", "vital_type", "observed_value"]`

### 1.3 LOW: `health.py` - Infrastructure Health

**File:** `backend/sense_loop/api/routes/health.py`
**Endpoints:** 2
**PHI Exposure:** None

No PHI accessed. Audit logging optional but recommended for security monitoring.

### 1.4 LOW: `value_sets.py` - Reference Data

**File:** `backend/sense_loop/api/routes/value_sets.py`
**PHI Exposure:** None

No PHI accessed. Audit logging optional.

---

## 2. Incomplete Audit Coverage

### 2.1 `patients.py` - Missing Endpoints

**File:** `backend/sense_loop/api/routes/patients.py`
**Current:** 6 of 10 endpoints have audit logging

| Endpoint | Method | Has Audit | Action Required |
|----------|--------|-----------|-----------------|
| `GET /patients` | GET | Yes | - |
| `POST /patients` | POST | Yes | - |
| `GET /patients/{id}` | GET | Yes | - |
| `PUT /patients/{id}` | PUT | Yes | - |
| `POST /patients/{id}/activate` | POST | Yes | - |
| `POST /patients/{id}/discharge` | POST | Yes | - |
| `GET /patients/{id}/vitals` | GET | **No** | Add PHI_VIEW |
| `GET /patients/{id}/workouts` | GET | **No** | Add PHI_VIEW |
| `GET /patients/{id}/sleep` | GET | **No** | Add PHI_VIEW |
| `GET /patients/{id}/devices` | GET | **No** | Add PHI_VIEW |

### 2.2 Other Routes - Spot Check Required

Review these files for completeness:
- `alerts.py` - Verify all alert actions logged
- `clinicians.py` - Verify role changes logged
- `questionnaires.py` - Verify template edits logged
- `instruction_templates.py` - Verify template modifications logged

---

## 3. Log Retention - CRITICAL

### Current Configuration

```typescript
// infra/sst.config.ts
const api = new sst.aws.Function("Api", {
  // ...
  logging: {
    retention: "1 month",  // LINE ~245
  },
});
```

### Required Change

```typescript
logging: {
  retention: "6 years",  // HIPAA minimum: 2190 days
},
```

### Additional Requirements

1. **S3 Archival**: Implement log archival to S3 with Glacier transition
2. **Immutability**: Enable S3 Object Lock for compliance records
3. **Encryption**: Ensure archived logs are encrypted (SSE-S3 or SSE-KMS)

### Implementation Steps

```bash
# 1. Update SST config
# Edit infra/sst.config.ts - change retention to "6 years"

# 2. Create S3 bucket for log archival
# Add to SST config:
const auditLogBucket = new sst.aws.Bucket("AuditLogs", {
  versioning: true,
  // Enable object lock for immutability
});

# 3. Set up CloudWatch Logs subscription to S3
# Use Lambda or Kinesis Firehose to stream logs to S3
```

---

## 4. Missing Audit Event Types

### 4.1 Authentication Events

Add to `backend/sense_loop/models/audit_log.py`:

```python
class AuditAction:
    # Existing...

    # Add these:
    SESSION_REFRESH = "session_refresh"
    SESSION_TIMEOUT = "session_timeout"
    SESSION_REVOKE = "session_revoke"
    MFA_CHALLENGE = "mfa_challenge"
    MFA_SUCCESS = "mfa_success"
    MFA_FAILURE = "mfa_failure"
```

### 4.2 Access Denial Events

Currently, 403 responses don't always generate audit logs. Add middleware to capture:

```python
# All authorization failures should log:
audit.log_denied(
    action=requested_action,
    resource_type=resource_type,
    resource_id=resource_id,
    reason="Cedar policy denied access",
)
```

### 4.3 Bulk Query Logging

For list endpoints that return multiple records, log the IDs accessed:

```python
# Example for patient list
audit.log(
    action=AuditAction.LIST,
    resource_type="patient",
    details={
        "returned_ids": [str(p.id) for p in patients],
        "total_count": len(patients),
        "filters": {"status": status, "search": search_term},
    },
    phi_fields_accessed=["full_name", "mrn", "date_of_birth"],
)
```

---

## 5. Implementation Checklist

### Phase 1: Critical (Block Production)

- [ ] **Add audit logging to `mobile.py`**
  - [ ] Import AuditLogger and context
  - [ ] Add logging to `/summary` endpoint
  - [ ] Add logging to `/care-plan` endpoint
  - [ ] Add logging to `/questionnaire/submit` endpoint
  - [ ] Add logging to all task endpoints
  - [ ] Add logging to device registration endpoints

- [ ] **Add audit logging to `dashboard.py`**
  - [ ] Import AuditLogger and context
  - [ ] Add logging to `/overview` endpoint
  - [ ] Add logging to `/critical-patients` with patient IDs
  - [ ] Add logging to `/recent-alerts` with alert IDs
  - [ ] Add logging to `/alerts-by-day` endpoint

- [ ] **Fix log retention**
  - [ ] Update `infra/sst.config.ts` retention to 6 years
  - [ ] Create S3 bucket for log archival
  - [ ] Set up CloudWatch to S3 streaming
  - [ ] Enable S3 Object Lock

### Phase 2: High Priority (Within 30 Days)

- [ ] **Complete `patients.py` audit coverage**
  - [ ] Add logging to vitals endpoint
  - [ ] Add logging to workouts endpoint
  - [ ] Add logging to sleep endpoint
  - [ ] Add logging to devices endpoint

- [ ] **Add session audit events**
  - [ ] Log session refresh/renewal
  - [ ] Log session timeout
  - [ ] Log forced session termination

- [ ] **Add authorization denial logging**
  - [ ] Create middleware for 403 responses
  - [ ] Log Cedar policy denials

### Phase 3: Medium Priority (Within 90 Days)

- [ ] **Implement log integrity verification**
  - [ ] Add hash chain to audit log entries
  - [ ] Create verification endpoint
  - [ ] Add integrity check to compliance reports

- [ ] **Add audit log access auditing**
  - [ ] Log when audit logs are queried
  - [ ] Track who accessed audit reports

- [ ] **Create compliance reporting**
  - [ ] PHI access report by user
  - [ ] Failed access attempt report
  - [ ] Emergency access report
  - [ ] Export activity report

---

## 6. Code Templates

### 6.1 Adding Audit to Mobile Endpoint

```python
# backend/sense_loop/api/routes/mobile.py

from sense_loop.audit import AuditLogger
from sense_loop.audit.context import AuditContext

@router.post("/summary")
async def get_summary(
    db: DbSession,
    request: SummaryRequest | None = None,
    patient=Depends(get_patient_from_token),
):
    # Create audit context for patient
    audit_context = AuditContext(
        actor_type="patient",
        actor_id=patient.id,
        actor_name=patient.full_name,
        actor_email=patient.email,
        organization_id=patient.organization_id,
        endpoint="/api/v1/sl/data/summary",
        http_method="POST",
    )
    audit = AuditLogger(db, audit_context)

    # ... existing code ...

    # Log PHI access
    audit.log_access(
        resource_type="patient_summary",
        resource_id=patient.id,
        resource_name=patient.full_name,
        phi_fields_accessed=[
            "heart_rate", "temperature", "blood_pressure",
            "weight", "sleep", "hrv", "activity"
        ],
    )

    return response
```

### 6.2 Adding Audit to Dashboard Endpoint

```python
# backend/sense_loop/api/routes/dashboard.py

from sense_loop.audit import AuditLogger, get_audit_context

@router.get("/critical-patients")
async def get_critical_patients(
    db: DbSession,
    practitioner: CurrentPractitioner,
    organization_id: UUID | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    audit = AuditLogger(db)

    # ... existing query code ...

    # Log access to patient PHI
    audit.log(
        action="list",
        resource_type="critical_patients",
        details={
            "patient_ids": [str(p.id) for p in patients],
            "count": len(patients),
            "organization_id": str(organization_id) if organization_id else None,
        },
        phi_fields_accessed=["full_name", "mrn", "status", "alert_count"],
    )

    return response
```

### 6.3 Middleware for Authorization Denials

```python
# backend/sense_loop/api/middleware/audit_middleware.py

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Log 403 responses
        if response.status_code == 403:
            # Extract context and log denial
            # Implementation depends on how context is passed
            pass

        return response
```

---

## 7. Testing Audit Logs

### Manual Verification

```sql
-- Check recent audit entries
SELECT
    created_at,
    actor_type,
    actor_name,
    action,
    resource_type,
    resource_id,
    outcome,
    phi_fields_accessed
FROM sl_audit_log
ORDER BY created_at DESC
LIMIT 50;

-- Check for gaps in mobile API logging
SELECT DISTINCT endpoint
FROM sl_audit_log
WHERE actor_type = 'patient'
AND created_at > NOW() - INTERVAL '24 hours';

-- Verify dashboard access logging
SELECT *
FROM sl_audit_log
WHERE resource_type IN ('critical_patients', 'recent_alerts', 'dashboard')
ORDER BY created_at DESC;
```

### Automated Tests

```python
# tests/audit/test_mobile_audit.py

async def test_summary_endpoint_creates_audit_log(client, patient_token, db):
    """Verify /summary endpoint creates audit entry."""
    response = await client.post(
        "/api/v1/sl/data/summary",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert response.status_code == 200

    # Check audit log was created
    audit_entry = db.query(AuditLog).filter(
        AuditLog.resource_type == "patient_summary",
        AuditLog.actor_type == "patient",
    ).order_by(AuditLog.created_at.desc()).first()

    assert audit_entry is not None
    assert "heart_rate" in audit_entry.phi_fields_accessed
```

---

## 8. Compliance Verification

After implementing all changes, verify:

1. **Every PHI access is logged** - Query audit_log for all resource types
2. **Logs are immutable** - Verify no UPDATE/DELETE on sl_audit_log table
3. **Retention is configured** - Check CloudWatch and S3 lifecycle policies
4. **Logs are encrypted** - Verify CloudWatch encryption settings
5. **Access to logs is audited** - Check audit_log for audit access queries

---

## References

- [HIPAA § 164.312(b) - Audit Controls](https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html)
- [NIST SP 800-92 - Guide to Computer Security Log Management](https://csrc.nist.gov/publications/detail/sp/800-92/final)
- [AWS CloudWatch Logs Retention](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/Working-with-log-groups-and-streams.html)
