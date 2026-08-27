# Open Wearables - Code Structure

*Where things live and how they're organized*

---

## Repository Layout

```
open-wearables/
├── backend/          → Python API server (FastAPI)
│   ├── app/          → Core open-wearables code (generic wearable platform)
│   └── sense_loop/   → Custom code for Recovery Companion app
├── frontend/         → React web dashboard
├── infra/            → AWS deployment configuration (SST)
└── docs/             → API documentation
```

**Important:** The `backend/` folder has two main parts:
- **`app/`** - The generic Open Wearables platform (wearable integrations, health data)
- **`sense_loop/`** - Custom code for the Recovery Companion app (patients, care plans, tasks, questionnaires)

---

## Backend (`/backend`)

The API server has **two main parts**:
1. **`app/`** - Generic Open Wearables platform (wearable data collection)
2. **`sense_loop/`** - Custom Recovery Companion code (patients, care plans, tasks)

---

## Backend - Core Platform (`/backend/app`)

The generic wearable health data platform.

### Directory Structure

```
backend/app/
├── api/              → HTTP endpoints (routes)
│   └── v1/           → Version 1 API
│       ├── users.py          → User CRUD operations
│       ├── connections.py    → Wearable device connections
│       ├── health_data.py    → Workouts, sleep, heart rate
│       ├── auth.py           → Login, tokens, API keys
│       └── webhooks.py       → Incoming provider webhooks
│
├── services/         → Business logic layer
│   ├── user_service.py       → User operations
│   ├── sync_service.py       → Data synchronization
│   ├── auth_service.py       → Authentication logic
│   └── health_score_service.py → Score calculations
│
├── repositories/     → Database access layer
│   ├── user_repository.py    → User queries
│   ├── event_record_repository.py → Workout/sleep queries
│   └── data_point_repository.py   → Time-series queries
│
├── models/           → Database table definitions
│   ├── user.py               → User table
│   ├── event_record.py       → Workouts, sleep events
│   ├── data_point.py         → Heart rate, steps, etc.
│   └── health_score.py       → Sleep/recovery scores
│
├── integrations/     → External service connections
│   ├── garmin/               → Garmin API integration
│   ├── fitbit/               → Fitbit API integration
│   ├── oura/                 → Oura API integration
│   ├── whoop/                → Whoop API integration
│   ├── medplum/              → Healthcare system integration
│   └── celery/               → Background task queue
│
├── schemas/          → API request/response formats
│
├── config.py         → Environment settings
└── database.py       → DB connection
```

---

## Backend - Sense Loop Extension (`/backend/sense_loop`)

**This is where all the custom Recovery Companion code lives.**

### Directory Structure

```
backend/sense_loop/
├── api/
│   └── routes/               → API endpoints for the app
│       ├── auth.py                   → Patient login, enrollment
│       ├── patients.py               → Patient management
│       ├── mobile.py                 → Mobile app endpoints
│       ├── dashboard.py              → Dashboard summary data
│       ├── questionnaires.py         → Check-in surveys
│       ├── health.py                 → Health data endpoints
│       ├── clinicians.py             → Clinician management
│       ├── alerts.py                 → Health alerts
│       └── settings.py               → App settings
│
├── services/                 → Business logic
│   ├── patient_service.py            → Patient CRUD
│   ├── enrollment_service.py         → Patient activation codes
│   ├── care_plan_service.py          → Discharge instructions
│   ├── task_generation_service.py    → Create daily tasks
│   ├── task_completion_service.py    → Mark tasks complete
│   ├── task_notification_service.py  → Task reminders
│   ├── questionnaire_service.py      → Check-in surveys
│   ├── summary_service.py            → Dashboard aggregation
│   ├── notification_service.py       → Push notifications
│   ├── alert_engine.py               → Health anomaly detection
│   └── practitioner_service.py       → Clinician management
│
├── models/                   → Database tables
│   ├── patient.py                    → Patient records
│   ├── care_plan.py                  → Care plans
│   ├── task.py                       → Daily tasks
│   ├── questionnaire.py              → Survey definitions
│   ├── questionnaire_response.py     → Survey answers
│   └── practitioner.py               → Clinician records
│
├── schemas/                  → API request/response formats
│
├── access/                   → Authorization policies
├── audit/                    → Audit logging
├── hooks/                    → Medplum webhook handlers
└── docs/                     → API documentation
```

### Key Services Explained

| Service | Purpose |
|---------|---------|
| `enrollment_service.py` | Handles activation codes, patient verification |
| `care_plan_service.py` | Manages discharge instructions from care team |
| `task_generation_service.py` | Creates daily tasks based on care plan |
| `task_notification_service.py` | Sends push reminders for tasks |
| `questionnaire_service.py` | Manages symptom check-in surveys |
| `summary_service.py` | Aggregates health data for dashboard |
| `alert_engine.py` | Detects health anomalies (HR spikes, etc.) |

---

## How They Work Together

```
┌─────────────────────────────────────────────────────────────┐
│                    Recovery Companion App                   │
└─────────────────────────────┬───────────────────────────────┘
                              │
         ┌────────────────────┴────────────────────┐
         │                                         │
         ▼                                         ▼
┌─────────────────────┐               ┌─────────────────────┐
│  sense_loop/api/    │               │     app/api/        │
│                     │               │                     │
│  • Patient login    │               │  • SDK auth         │
│  • Care plans       │               │  • Health data sync │
│  • Tasks            │               │  • Wearable OAuth   │
│  • Questionnaires   │               │  • Webhooks         │
│  • Dashboard        │               │                     │
└─────────┬───────────┘               └──────────┬──────────┘
          │                                      │
          └──────────────┬───────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Shared Database    │
              │  (PostgreSQL)       │
              └─────────────────────┘
```

---

## Migrations (`/backend/migrations`)

Database schema changes using Alembic.

```
backend/migrations/
└── versions/         → Individual migration files
    ├── 2026_08_13_..._add_refresh_token_replacement.py
    ├── 2026_07_..._add_patient_tables.py
    └── ...
```

### Architecture Pattern

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Request   │ ──► │     API     │ ──► │   Service   │ ──► │ Repository  │
│  (HTTP)     │     │  (Routes)   │     │  (Logic)    │     │ (Database)  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                          │
                          ▼
                    ┌─────────────┐
                    │   Schema    │
                    │ (Validate)  │
                    └─────────────┘
```

**Flow example - Get user's workouts:**
1. Request hits `/api/v1/users/{id}/workouts`
2. `api/v1/health_data.py` handles the route
3. Calls `services/health_data_service.py` for business logic
4. Service calls `repositories/event_record_repository.py` for DB query
5. Returns data formatted by `schemas/health_data_schema.py`

---

## Frontend (`/frontend`)

React web dashboards. The frontend has **two main parts**:
1. **Standard routes** - Generic Open Wearables developer dashboard
2. **`sl/` routes** - Custom Recovery Companion clinician dashboard

### Directory Structure

```
frontend/src/
├── routes/                      → Page components (TanStack Router)
│   │
│   ├── _authenticated/          → Developer dashboard (protected)
│   │   ├── dashboard.tsx                → Main developer dashboard
│   │   ├── users.tsx                    → User management layout
│   │   ├── users/index.tsx              → User list
│   │   ├── users/$userId.tsx            → User detail view
│   │   ├── webhooks.tsx                 → Webhook management
│   │   ├── webhooks/index.tsx           → Webhook list
│   │   ├── webhooks/$endpointId.tsx     → Webhook detail
│   │   └── settings.tsx                 → Developer settings
│   │       ├── -credentials-tab.tsx         → API keys
│   │       ├── -providers-tab.tsx           → Wearable providers
│   │       ├── -team-tab.tsx                → Team members
│   │       ├── -security-tab.tsx            → Security options
│   │       ├── -data-lifecycle-tab.tsx      → Data retention
│   │       ├── -priorities-tab.tsx          → Data priorities
│   │       └── -seed-data-tab.tsx           → Test data
│   │
│   ├── sl/                      → Clinician Dashboard (Recovery Companion)
│   │   ├── login.tsx                    → Clinician login
│   │   ├── forgot-password.tsx          → Password recovery
│   │   ├── set-password/                → Invite acceptance
│   │   │
│   │   └── _sl-authenticated/           → Protected clinician routes
│   │       ├── dashboard.tsx                → Clinician home (patient overview)
│   │       ├── patients/index.tsx           → Patient list
│   │       ├── patients/$patientId.tsx      → Patient detail
│   │       ├── patients/$patientId/index.tsx
│   │       ├── patients/$patientId/plans.$planId.edit.tsx  → Edit care plan
│   │       ├── patients/$patientId/questionnaires.$questionnaireId.edit.tsx
│   │       ├── clinicians/index.tsx         → Clinician list
│   │       ├── clinicians/$clinicianId.tsx  → Clinician detail
│   │       ├── alerts/index.tsx             → Health alerts list
│   │       ├── alerts/$alertId.tsx          → Alert detail
│   │       ├── instruction-templates/index.tsx  → Care plan templates
│   │       ├── instruction-templates/$templateId.tsx
│   │       ├── instruction-templates/questionnaires.$questionnaireId.tsx
│   │       └── settings.tsx                 → Clinician settings
│   │
│   ├── users/$userId/pair.tsx   → Device pairing flow (public)
│   ├── login.tsx                → Developer login
│   ├── register.tsx             → Developer registration
│   ├── forgot-password.tsx      → Developer password reset
│   ├── accept-invite.tsx        → Team invite acceptance
│   └── widget.connect.tsx       → Embeddable connection widget
│
├── components/              → Reusable UI components
│   ├── ui/                          → Base components (shadcn/ui)
│   ├── data-table.tsx               → Generic data table
│   ├── nav.tsx                      → Navigation sidebar
│   └── sl/                          → Clinician-specific components
│
├── lib/                     → Utilities
│   ├── api.ts                       → API client
│   ├── auth.ts                      → Auth helpers
│   └── sl-api.ts                    → Clinician API client
│
└── styles/                  → CSS files
```

### Two Dashboards

| Dashboard | URL Path | Users | Purpose |
|-----------|----------|-------|---------|
| **Developer** | `/dashboard` | API developers | Manage users, connections, webhooks |
| **Clinician** | `/sl/dashboard` | Care team | Monitor patients, view alerts |

### Tech Stack
- **React 19** - UI framework
- **TanStack Router** - File-based routing
- **TanStack Query** - Data fetching/caching
- **Tailwind CSS** - Styling
- **shadcn/ui** - Component library

---

## Infrastructure (`/infra`)

AWS deployment using SST (Serverless Stack).

### Directory Structure

```
infra/
├── sst.config.ts         → Main infrastructure definition
├── package.json          → SST dependencies
├── scripts/
│   └── check-secrets.sh  → Validates required secrets
└── .sst/
    └── outputs.json      → Deployed resource info (URLs, IDs)
```

### What Gets Deployed

```
┌────────────────────────────────────────────────────────────┐
│                        AWS Account                         │
│                                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   VPC (Network)                     │   │
│  │                                                     │   │
│  │  ┌──────────────────────────────────────────────┐   │   │
│  │  │           ECS Fargate (Containers)           │   │   │
│  │  │                                              │   │   │
│  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐       │   │   │
│  │  │  │   API   │  │ Worker  │  │  Beat   │       │   │   │
│  │  │  │ Service │  │ Service │  │ Service │       │   │   │
│  │  │  └─────────┘  └─────────┘  └─────────┘       │   │   │
│  │  └──────────────────────────────────────────────┘   │   │
│  │                                                     │   │
│  │  ┌─────────────────┐    ┌─────────────────────┐     │   │
│  │  │  RDS PostgreSQL │    │  ElastiCache Redis  │     │   │
│  │  │   (Database)    │    │      (Cache)        │     │   │
│  │  └─────────────────┘    └─────────────────────┘     │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                            │
│  ┌─────────────────┐    ┌─────────────────────────────┐    │
│  │ Load Balancer   │    │  S3 + CloudFront (Frontend) │    │
│  │ (HTTPS routing) │    │      (Static hosting)       │    │
│  └─────────────────┘    └─────────────────────────────┘    │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### Key Services

| Service | Purpose | Scaling |
|---------|---------|---------|
| **API** | Handles HTTP requests | 1-10 instances |
| **Worker** | Background jobs (sync, emails) | 1-5 instances |
| **Beat** | Scheduled tasks (hourly sync) | 1 instance only |

---

## Database Tables (Key Models)

```
┌─────────────────┐       ┌─────────────────┐
│      user       │       │ user_connection │
├─────────────────┤       ├─────────────────┤
│ id              │──────►│ user_id         │
│ external_id     │       │ provider        │
│ email           │       │ access_token    │
│ created_at      │       │ refresh_token   │
└─────────────────┘       └─────────────────┘
        │
        │
        ▼
┌─────────────────┐       ┌─────────────────┐
│  event_record   │       │data_point_series│
├─────────────────┤       ├─────────────────┤
│ user_id         │       │ user_id         │
│ type (workout/  │       │ type (heart_rate│
│       sleep)    │       │       /steps)   │
│ start_time      │       │ timestamp       │
│ end_time        │       │ value           │
│ calories        │       │ source          │
│ heart_rate_avg  │       └─────────────────┘
└─────────────────┘

┌─────────────────┐       ┌─────────────────┐
│  health_score   │       │    api_key      │
├─────────────────┤       ├─────────────────┤
│ user_id         │       │ developer_id    │
│ type (sleep/    │       │ key_hash        │
│       recovery) │       │ name            │
│ score           │       │ last_used       │
│ components      │       │ is_active       │
└─────────────────┘       └─────────────────┘
```

---

## Background Jobs (Celery)

Located in `/backend/app/integrations/celery/`

### Task Types

| Task | Trigger | Purpose |
|------|---------|---------|
| `sync_user_data` | Hourly (Beat) | Pull latest from wearable APIs |
| `process_webhook` | Incoming webhook | Handle provider notifications |
| `send_email` | API request | Send transactional emails |
| `calculate_scores` | After sync | Compute health scores |

### Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    Beat     │ ──► │    Redis    │ ──► │   Worker    │
│ (Scheduler) │     │   (Queue)   │     │ (Executor)  │
└─────────────┘     └─────────────┘     └─────────────┘
```

---

## Wearable Integrations

Located in `/backend/app/integrations/`

Each provider has its own folder:

```
integrations/
├── garmin/
│   ├── client.py         → API client
│   ├── auth.py           → OAuth flow
│   ├── sync.py           → Data sync logic
│   └── models.py         → Garmin-specific types
│
├── fitbit/
│   └── ... (same structure)
│
├── oura/
│   └── ...
│
└── whoop/
    └── ...
```

### OAuth Flow (for cloud providers)

```
1. User clicks "Connect Garmin"
2. Redirect to Garmin login page
3. User authorizes
4. Garmin redirects back with auth code
5. Backend exchanges code for tokens
6. Stores tokens in user_connection table
7. Background worker syncs data hourly
```

---

## Key Files to Know

| File | Purpose |
|------|---------|
| `backend/app/main.py` | API entry point |
| `backend/app/core/config.py` | Environment variables |
| `backend/app/api/v1/__init__.py` | Route registration |
| `infra/sst.config.ts` | Infrastructure definition |
| `backend/alembic.ini` | Database migration config |

---

## Common Operations

### Adding a new Recovery Companion feature
1. Create route in `backend/sense_loop/api/routes/`
2. Add service logic in `backend/sense_loop/services/`
3. Add models in `backend/sense_loop/models/`
4. Define schemas in `backend/sense_loop/schemas/`
5. Create migration if new tables needed

### Adding a new wearable provider
1. Create folder in `backend/app/integrations/`
2. Implement OAuth client
3. Implement sync logic
4. Add webhook handler (if supported)
5. Register in provider enum

### Deploying changes
```bash
cd infra
npm run deploy:pre-pilot   # Staging (~$130-150/month)
npm run deploy:production  # Production
```

### Running database migrations
```bash
cd backend
alembic upgrade head       # Apply migrations
alembic revision -m "..."  # Create new migration
```

---

## Database Schema

The database has **two sets of tables**:
1. **Core tables** (`app/models/`) - Generic wearable platform
2. **Sense Loop tables** (`sense_loop/models/`) - Recovery Companion custom

### Core Platform Tables

```
┌─────────────────────┐       ┌─────────────────────┐
│        user         │       │   user_connection   │
├─────────────────────┤       ├─────────────────────┤
│ id                  │──────►│ user_id             │
│ external_id         │       │ provider (garmin,   │
│ email               │       │   fitbit, oura...)  │
│ application_id      │       │ access_token        │
│ created_at          │       │ refresh_token       │
└─────────────────────┘       │ token_expires_at    │
        │                     └─────────────────────┘
        │
        ├──────────────────────────────────────────────┐
        │                      │                       │
        ▼                      ▼                       ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│    event_record     │ │  data_point_series  │ │    health_score     │
├─────────────────────┤ ├─────────────────────┤ ├─────────────────────┤
│ user_id             │ │ user_id             │ │ user_id             │
│ type (workout,      │ │ type (heart_rate,   │ │ type (sleep,        │
│       sleep)        │ │       steps, hrv)   │ │       recovery)     │
│ start_time          │ │ timestamp           │ │ date                │
│ end_time            │ │ value               │ │ score               │
│ calories            │ │ source              │ │ components (json)   │
│ heart_rate_avg      │ │ provider            │ └─────────────────────┘
│ provider            │ └─────────────────────┘
└─────────────────────┘

┌─────────────────────┐       ┌─────────────────────┐
│     developer       │       │       api_key       │
├─────────────────────┤       ├─────────────────────┤
│ id                  │──────►│ developer_id        │
│ email               │       │ key_hash            │
│ password_hash       │       │ name                │
│ name                │       │ last_used_at        │
└─────────────────────┘       │ is_active           │
                              └─────────────────────┘

┌─────────────────────┐       ┌─────────────────────┐
│     application     │       │   refresh_token     │
├─────────────────────┤       ├─────────────────────┤
│ id                  │       │ token_hash          │
│ developer_id        │       │ user_id             │
│ name                │       │ expires_at          │
│ webhook_url         │       │ is_revoked          │
└─────────────────────┘       │ replaced_by_id      │
                              └─────────────────────┘
```

### Recovery Companion Tables (Sense Loop)

```
┌─────────────────────┐       ┌─────────────────────┐
│      patient        │       │     practitioner    │
├─────────────────────┤       ├─────────────────────┤
│ id                  │       │ id                  │
│ user_id (→ user)    │       │ email               │
│ email               │       │ first_name          │
│ first_name          │       │ last_name           │
│ last_name           │       │ password_hash       │
│ date_of_birth       │       │ organization_id     │
│ phone_last_4        │       │ is_active           │
│ activation_code     │       └─────────────────────┘
│ enrollment_status   │               │
│ discharge_date      │               │
│ push_token (FCM)    │               ▼
└─────────────────────┘       ┌─────────────────────┐
        │                     │  practitioner_role  │
        │                     ├─────────────────────┤
        │                     │ practitioner_id     │
        ├────────────────────►│ patient_id          │
        │                     │ role (primary,      │
        │                     │       care_team)    │
        │                     └─────────────────────┘
        │
        ├──────────────────────────────────────────────┐
        │                      │                       │
        ▼                      ▼                       ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│ patient_instruction │ │ patient_instruction │ │    questionnaire    │
│       _plan         │ │       _task         │ │      _response      │
├─────────────────────┤ ├─────────────────────┤ ├─────────────────────┤
│ patient_id          │ │ plan_id             │ │ patient_id          │
│ template_id         │ │ instruction_text    │ │ questionnaire_id    │
│ start_date          │ │ scheduled_date      │ │ submitted_at        │
│ end_date            │ │ scheduled_time      │ │ answers (json)      │
│ is_active           │ │ status (pending,    │ └─────────────────────┘
└─────────────────────┘ │         completed)  │
                        │ completed_at        │
                        └─────────────────────┘

┌─────────────────────┐       ┌─────────────────────┐
│   questionnaire     │       │        alert        │
├─────────────────────┤       ├─────────────────────┤
│ id                  │       │ patient_id          │
│ title               │       │ type (hr_spike,     │
│ description         │       │       sleep_drop)   │
│ questions (json)    │       │ severity (low,      │
│ frequency           │       │   medium, high)     │
│ is_active           │       │ triggered_at        │
└─────────────────────┘       │ resolved_at         │
                              │ resolved_by_id      │
                              │ notes               │
                              └─────────────────────┘

┌─────────────────────┐       ┌─────────────────────┐
│ instruction_template│       │    audit_log        │
├─────────────────────┤       ├─────────────────────┤
│ id                  │       │ actor_type          │
│ name                │       │ actor_id            │
│ category            │       │ action              │
│ instructions (json) │       │ resource_type       │
│ organization_id     │       │ resource_id         │
│ is_active           │       │ changes (json)      │
└─────────────────────┘       │ created_at          │
                              └─────────────────────┘
```

### Key Relationships

| Relationship | Description |
|--------------|-------------|
| `user` → `patient` | Each patient has an underlying user account |
| `patient` → `practitioner_role` | Clinicians assigned to monitor patient |
| `patient` → `patient_instruction_plan` | Active care plans |
| `plan` → `patient_instruction_task` | Daily tasks generated from plan |
| `patient` → `questionnaire_response` | Submitted check-in surveys |
| `patient` → `alert` | Health anomalies detected |
| `user` → `event_record` | Workouts and sleep sessions |
| `user` → `data_point_series` | Time-series health metrics |
