# Sense Loop Extension for Open Wearables

Clinical extension module providing patient monitoring, alert management, and care coordination.

## Directory Structure

```
sense_loop/
├── __init__.py           # Package init with version
├── config.py             # Extension settings (SL_ prefixed env vars)
│
├── models/               # SQLAlchemy models (sl_ table prefix)
│   ├── organization.py   # Multi-tenant organizations
│   ├── role_definition.py # Flexible RBAC roles
│   ├── practitioner.py   # Clinical staff (own auth)
│   ├── practitioner_role.py # Links practitioner to org+role
│   ├── practitioner_invite.py # Pending invitations
│   ├── patient.py        # Links to OW User
│   ├── alert_protocol.py # Immutable versioned rules (SaMD)
│   ├── alert.py          # Generated alerts with traceability
│   ├── patient_summary.py # O(1) dashboard queries
│   ├── care_plan.py      # Discharge instructions
│   ├── questionnaire.py  # Assessment templates
│   ├── questionnaire_response.py # Patient responses
│   └── audit_log.py      # HIPAA audit trail
│
├── services/             # Business logic
│   ├── patient_service.py # Patient CRUD
│   ├── enrollment_service.py # Activation codes, verification
│   ├── practitioner_service.py # Clinician CRUD
│   ├── practitioner_auth_service.py # Practitioner login
│   ├── invite_service.py # Clinician invitations
│   ├── alert_engine.py   # Deterministic thresholds (SaMD)
│   ├── summary_service.py # PatientSummary updates
│   ├── care_plan_service.py
│   ├── questionnaire_service.py
│   ├── notification_service.py # SMS/email/push
│   └── fhir_export_service.py # On-demand FHIR export
│
├── api/routes/           # FastAPI endpoints
│   ├── auth.py           # Patient & practitioner auth
│   ├── mobile.py         # iOS app data endpoints
│   ├── patients.py       # Patient management
│   ├── alerts.py         # Alert management
│   ├── clinicians.py     # Clinician management + invites
│   ├── organizations.py  # Org management
│   ├── dashboard.py      # Dashboard aggregations
│   └── health.py         # Celery health check for monitoring
│
├── access/               # RBAC system
│   ├── permissions.py    # Permission constants
│   └── policy_engine.py  # Access control logic
│
├── audit/                # HIPAA audit system
│   ├── context.py        # Request context tracking
│   ├── logger.py         # Audit event logging
│   └── middleware.py     # Auto-capture requests
│
├── hooks/                # OW integration
│   └── data_events.py    # Subscribe to OW data events
│
└── schemas/              # Pydantic schemas
    ├── patient.py
    ├── alert.py
    ├── mobile.py         # iOS response formats
    ├── auth.py
    ├── organization.py
    ├── practitioner.py
    └── errors.py
```

## Configuration

Enable the extension in `.env`:

```env
SENSE_LOOP_ENABLED=true
```

Optional settings (SL_ prefix):

```env
SL_ACTIVATION_CODE_LENGTH=8
SL_ACTIVATION_CODE_EXPIRE_HOURS=72
SL_INVITE_EXPIRE_HOURS=24
SL_SENDGRID_API_KEY=your-key
```

## Database Tables

All tables use `sl_` prefix:

- `sl_organization` - Multi-tenant organizations
- `sl_role_definition` - Flexible roles with permissions
- `sl_practitioner` - Clinical staff (own auth)
- `sl_practitioner_role` - Practitioner-org-role links
- `sl_practitioner_invite` - Pending invitations
- `sl_patient` - Links to OW User
- `sl_alert_protocol` - Immutable versioned alert rules
- `sl_alert_protocol_rule` - Individual threshold rules
- `sl_alert_risk_window` - Post-op risk windows
- `sl_alert` - Generated alerts
- `sl_patient_summary` - Pre-computed vitals
- `sl_care_plan` - Patient care plans
- `sl_questionnaire` - Assessment templates
- `sl_questionnaire_question` - Individual questions
- `sl_questionnaire_response` - Patient responses
- `sl_questionnaire_answer` - Individual answers
- `sl_audit_log` - HIPAA audit trail

## API Endpoints

### Patient Auth (public)
- `POST /api/v1/sl/auth/patient/validate-code`
- `POST /api/v1/sl/auth/patient/activate`
- `POST /api/v1/sl/auth/patient/set-password`
- `POST /api/v1/sl/auth/patient/login`

### Practitioner Auth (public)
- `POST /api/v1/sl/auth/practitioner/login`
- `POST /api/v1/sl/auth/practitioner/logout`
- `POST /api/v1/sl/auth/practitioner/forgot-password`
- `POST /api/v1/sl/auth/practitioner/reset-password`

### Mobile Data (SDK token required)
- `POST /api/v1/sl/data/summary`
- `POST /api/v1/sl/data/care-plan`
- `POST /api/v1/sl/data/questionnaire/submit`

### Dashboard (Practitioner token required)
- `GET/POST /api/v1/sl/patients`
- `GET /api/v1/sl/alerts`
- `POST /api/v1/sl/alerts/{id}/acknowledge`
- `POST /api/v1/sl/alerts/{id}/resolve`
- `GET/POST /api/v1/sl/organizations`
- `GET /api/v1/sl/clinicians`
- `POST /api/v1/sl/clinicians/invite`
- `GET /api/v1/sl/dashboard/overview`

### Health Check (no auth required)
- `GET /api/v1/sl/health/celery` - Full Celery worker and queue status
- `GET /api/v1/sl/health/celery/simple` - Simple pass/fail for uptime monitors

## Setup

1. Enable extension in `.env`:
   ```
   SENSE_LOOP_ENABLED=true
   ```

2. Run migrations:
   ```bash
   alembic upgrade head
   ```

3. Seed default roles:
   ```bash
   python scripts/seed_sl_roles.py
   ```

## SaMD Compliance

The alert engine (`services/alert_engine.py`) is designed for FDA SaMD Class II compliance:

- **Deterministic**: No ML/AI - explicit numeric thresholds only
- **Traceable**: Every alert includes protocol/rule/window traceability
- **Versioned**: Protocols are immutable once published
- **Auditable**: All evaluations can be reconstructed

Changes to the alert engine require design review and regulatory approval.

## Operations & Monitoring

### Celery Health Check

The `/api/v1/sl/health/celery` endpoint monitors Celery worker health and queue status.

**Full endpoint** returns detailed status:
```json
{
  "status": "healthy",
  "workers": [
    {"name": "celery@hostname", "status": "online", "queues": ["default", "sdk_sync", ...]}
  ],
  "queues": [
    {"name": "default", "length": 0, "status": "ok"},
    {"name": "sdk_sync", "length": 0, "status": "ok"}
  ],
  "message": "1 worker(s) online, all queues clear",
  "checked_at": "2026-06-16T18:48:53Z"
}
```

**Simple endpoint** (`/api/v1/sl/health/celery/simple`) for uptime monitors:
```json
{"status": "healthy", "message": "1 worker(s) online, all queues clear", "workers_online": 1}
```

**Status values:**
- `healthy` - All workers online, no queue backlog
- `degraded` - Some workers offline OR queue length > 100 (warning)
- `unhealthy` - No workers online OR queue length > 500 (critical)

### Monitoring Setup

1. **External uptime monitoring** (Pingdom, UptimeRobot, etc.):
   - Monitor `/api/v1/sl/health/celery/simple`
   - Alert when `status` is not `healthy`

2. **Cron-based alerting** (example):
   ```bash
   # Check every 5 minutes, alert if unhealthy
   */5 * * * * curl -s http://localhost:8001/api/v1/sl/health/celery/simple | \
     jq -e '.status == "healthy"' > /dev/null || \
     echo "Celery unhealthy" | mail -s "Alert: Celery Down" ops@example.com
   ```

3. **Process supervision** - Use systemd, supervisord, or Docker restart policies to auto-restart workers:
   ```yaml
   # docker-compose.yml example
   celery-worker:
     command: celery -A app.main:celery_app worker --loglevel=info
     restart: always
     healthcheck:
       test: ["CMD", "celery", "-A", "app.main:celery_app", "inspect", "ping", "-t", "10"]
       interval: 30s
       timeout: 10s
       retries: 3
   ```

### Queue Thresholds

| Queue | Warning (>100) | Critical (>500) |
|-------|----------------|-----------------|
| `default` | Tasks backing up | Workers likely down |
| `sdk_sync` | HealthKit syncs delayed | Data not being processed |
| `garmin_sync` | Garmin syncs delayed | Data not being processed |
| `webhook_sync` | Webhooks delayed | External systems not notified |
