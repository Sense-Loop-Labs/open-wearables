# Sense Loop Fork Changes

This document tracks all modifications made to the upstream [Open Wearables](https://github.com/the-momentum/open-wearables) repository for the Sense Loop FHIR integration.

## Overview

The Sense Loop fork adds Medplum FHIR integration alongside the existing Svix webhook system. The goal is to keep changes **additive** where possible to minimize merge conflicts with upstream updates.

## Change Categories

### 1. Purely Additive (No Conflict Risk)

These are new files that don't exist upstream:

| Path | Purpose |
|------|---------|
| `backend/app/services/medplum/` | Medplum integration module |
| `backend/app/services/medplum/__init__.py` | Module exports |
| `backend/app/services/medplum/webhook.py` | OAuth2 webhook client |
| `backend/app/services/medplum/hr_processor.py` | HR anomaly detection |
| `backend/app/services/medplum/context_detector.py` | Activity context detection |
| `backend/app/integrations/celery/tasks/medplum_tasks.py` | Celery tasks for Medplum |
| `FORK_CHANGES.md` | This file |

### 2. Appended Configuration (Low Conflict Risk)

Settings added to the end of existing config:

| File | Changes |
|------|---------|
| `backend/app/config.py` | Added `medplum_*` settings after Svix settings |

### 3. Extended Imports/Exports (Low Conflict Risk)

| File | Changes |
|------|---------|
| `backend/app/integrations/celery/tasks/__init__.py` | Added Medplum task imports and `__all__` exports |

### 4. Modified Upstream Files (Merge Conflict Risk)

These files have behavioral changes that may conflict with upstream updates:

#### `backend/app/services/outgoing_webhooks/events.py`

**Changes:**
- Added `from app.config import settings` import
- Added Medplum dispatch functions:
  - `_dispatch_medplum_workout()`
  - `_dispatch_medplum_sleep()`
  - `_dispatch_medplum_hr()`
  - `_dispatch_medplum_vitals()`
- Modified `on_workout_created()` - added `medplum_patient_id` parameter and Medplum dispatch call
- Modified `on_sleep_created()` - added `medplum_patient_id` parameter and Medplum dispatch call
- Modified `on_timeseries_batch_saved()` - added `medplum_patient_id` and `source_device` parameters, added HR and vitals dispatch to Medplum

**Merge Strategy:** When upstream modifies these functions, ensure the Medplum dispatch calls are preserved.

#### `backend/app/services/event_record_service.py`

**Changes:**
- `_emit_event_record_webhook()`: Removed Svix gatekeeping check (commented out)
- `bulk_create_details()`: Removed Svix gatekeeping check (commented out)

**Why:** Upstream assumes "no Svix = no webhooks". We changed it so each dispatcher handles its own enablement, allowing Medplum to work independently of Svix.

**Marked with:** `# Sense Loop Fork:` comments showing original code

#### `backend/app/services/timeseries_service.py`

**Changes:**
- `_start_webhook_thread()`: Removed Svix gatekeeping check (commented out)

**Why:** Same as above - allows Medplum webhooks to fire even when Svix is disabled.

**Marked with:** `# Sense Loop Fork:` comments showing original code

#### `docker-compose.yml`

**Changes:**
- Changed postgres port: `5432:5432` → `5433:5432` (avoid conflict with sense-loop-fhir)
- Changed redis port: `6379:6379` → `6380:6379` (avoid conflict with sense-loop-fhir)
- Added external network for inter-service communication:
  ```yaml
  networks:
    default:
      name: sense-loop
      external: true
  ```

**Note:** This is local dev only. Production uses separate infrastructure.

## Syncing with Upstream

### Before Merging

```bash
# Fetch upstream changes
git fetch upstream

# See what changed
git log HEAD..upstream/main --oneline

# Check for conflicts in modified files
git diff HEAD...upstream/main -- \
  backend/app/services/outgoing_webhooks/events.py \
  backend/app/services/event_record_service.py \
  backend/app/services/timeseries_service.py \
  backend/app/config.py
```

### Merge Process

```bash
git checkout main
git merge upstream/main
```

### Resolving Conflicts

1. **Svix checks:** If upstream changes the areas around our commented-out Svix checks, ensure the comments are preserved and the check remains disabled.

2. **events.py functions:** If upstream modifies `on_workout_created`, `on_sleep_created`, or `on_timeseries_batch_saved`:
   - Keep our added parameters (`medplum_patient_id`, `source_device`)
   - Keep our Medplum dispatch calls at the end of each function

3. **config.py:** Our Medplum settings are at the end - should merge cleanly unless upstream adds settings in the same location.

## Environment Variables (Sense Loop Additions)

```bash
# Medplum FHIR Integration
MEDPLUM_WEBHOOK_URL=http://sense-loop-medplum:8103/fhir/R4/$process-wearable-data
MEDPLUM_CLIENT_ID=your-client-id
MEDPLUM_CLIENT_SECRET=your-client-secret
MEDPLUM_ENABLED=true

# HR Anomaly Detection Thresholds
MEDPLUM_HR_ANOMALY_SUSTAINED_SECONDS=300
MEDPLUM_HR_BUFFER_TTL_HOURS=2
MEDPLUM_HR_HIGH_RESTING=100
MEDPLUM_HR_HIGH_ACTIVE=150
MEDPLUM_HR_HIGH_EXERCISE=180
MEDPLUM_HR_LOW_RESTING=50
MEDPLUM_HR_LOW_SLEEPING=40
```

## Testing After Merge

After merging upstream changes:

1. **Verify Medplum tasks registered:**
   ```bash
   docker exec celery-worker__open-wearables celery -A app.integrations.celery inspect registered | grep medplum
   ```

2. **Test workout webhook:**
   - Create a workout via HealthKit sync
   - Verify it appears in Medplum as an Observation

3. **Test HR processing:**
   - Sync HR data
   - Check Celery logs for `process_hr_for_medplum` task execution

## Architecture Decision

**Why modify Svix checks instead of wrapping them?**

The upstream code gates ALL webhook dispatch behind Svix enablement:
```python
if not svix_service.is_enabled():
    return  # Blocks everything
```

Options considered:
1. **Wrap existing functions** - Would require duplicating dispatch logic
2. **Add Medplum check alongside Svix** - Couples the two systems
3. **Remove gatekeeping, let each dispatcher decide** - Cleanest separation

We chose option 3. Each dispatcher (`_dispatch()` for Svix, `_dispatch_medplum_*()` for Medplum) checks its own enablement. This is more flexible and follows single-responsibility principle.
