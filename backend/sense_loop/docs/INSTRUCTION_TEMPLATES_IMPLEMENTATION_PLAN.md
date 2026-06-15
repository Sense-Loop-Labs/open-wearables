# Instruction Templates - Implementation Plan

> **Created**: 2025-06-11
> **Status**: Ready for implementation
> **Estimated Scope**: ~15-20 files, 4 phases

## Overview

This plan implements a flexible instruction template system supporting:
- Post-surgical discharge instructions
- Chronic condition management (hypertension, diabetes, etc.)
- Automated task generation with smart completion detection
- Intelligent notifications (reminders, overdue alerts, confirmations)

---

## Phase 1: Data Models & Migrations

### 1.1 Database Migrations

**File**: `backend/migrations/versions/YYYY_MM_DD_HHMM-add_instruction_template_tables.py`

Create the following tables:

#### sl_activity_template
```python
op.create_table(
    "sl_activity_template",
    sa.Column("id", sa.UUID(), primary_key=True),
    sa.Column("organization_id", sa.UUID(), sa.ForeignKey("sl_organization.id"), nullable=True, index=True),

    # Metadata
    sa.Column("name", sa.String(100), unique=True, nullable=False),
    sa.Column("title", sa.String(255), nullable=False),
    sa.Column("description", sa.Text(), nullable=False),
    sa.Column("status", sa.String(20), default="draft"),  # draft, active, retired
    sa.Column("version", sa.String(20), default="1.0.0"),

    # Classification
    sa.Column("category_code", sa.String(50), nullable=False),  # wound-care, medications, etc.
    sa.Column("kind", sa.String(50), default="task"),  # task, service_request, medication_request

    # Task completion settings
    sa.Column("completion_method", sa.String(20), default="manual"),  # auto, manual, hybrid
    sa.Column("data_trigger_types", sa.ARRAY(sa.String()), nullable=True),  # ["blood_pressure"]
    sa.Column("data_threshold", sa.JSON(), nullable=True),  # {"min_steps": 500}
    sa.Column("confirmation_prompt", sa.String(500), nullable=True),

    # Content
    sa.Column("content", sa.JSON(), default=dict),
    sa.Column("default_timing", sa.JSON(), nullable=True),

    # FHIR interop
    sa.Column("code_system", sa.String(255), nullable=True),
    sa.Column("code_value", sa.String(50), nullable=True),

    # Audit
    sa.Column("created_by_id", sa.UUID(), sa.ForeignKey("sl_practitioner.id"), nullable=False),
    sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
)
```

#### sl_instruction_template
```python
op.create_table(
    "sl_instruction_template",
    sa.Column("id", sa.UUID(), primary_key=True),
    sa.Column("organization_id", sa.UUID(), sa.ForeignKey("sl_organization.id"), nullable=True, index=True),

    # Metadata
    sa.Column("name", sa.String(100), unique=True, nullable=False),
    sa.Column("title", sa.String(255), nullable=False),
    sa.Column("description", sa.Text(), nullable=False),
    sa.Column("status", sa.String(20), default="draft"),
    sa.Column("version", sa.String(20), default="1.0.0"),

    # Content
    sa.Column("content", sa.JSON(), default=dict),  # Sections and items

    # Notification defaults
    sa.Column("notification_config", sa.JSON(), nullable=True),

    # Audit
    sa.Column("created_by_id", sa.UUID(), sa.ForeignKey("sl_practitioner.id"), nullable=False),
    sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
)
```

#### sl_instruction_template_health_focus
```python
op.create_table(
    "sl_instruction_template_health_focus",
    sa.Column("id", sa.UUID(), primary_key=True),
    sa.Column("template_id", sa.UUID(), sa.ForeignKey("sl_instruction_template.id", ondelete="CASCADE"), index=True),
    sa.Column("health_focus_code", sa.String(100), nullable=False),
    sa.UniqueConstraint("template_id", "health_focus_code"),
)
```

#### sl_patient_instruction_plan
```python
op.create_table(
    "sl_patient_instruction_plan",
    sa.Column("id", sa.UUID(), primary_key=True),
    sa.Column("patient_id", sa.UUID(), sa.ForeignKey("sl_patient.id", ondelete="CASCADE"), index=True),
    sa.Column("template_id", sa.UUID(), sa.ForeignKey("sl_instruction_template.id"), index=True),

    # Status
    sa.Column("status", sa.String(20), default="active"),  # draft, active, completed, cancelled
    sa.Column("effective_start", sa.DateTime(), nullable=False),
    sa.Column("effective_end", sa.DateTime(), nullable=True),

    # Customizations
    sa.Column("customizations", sa.JSON(), nullable=True),

    # Resolved content (denormalized for fast reads)
    sa.Column("resolved_content", sa.JSON(), default=dict),

    # Task generation tracking
    sa.Column("tasks_generated_through", sa.Date(), nullable=True),

    # Audit
    sa.Column("assigned_by_id", sa.UUID(), sa.ForeignKey("sl_practitioner.id"), nullable=False),
    sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
)
```

#### sl_patient_instruction_task
```python
op.create_table(
    "sl_patient_instruction_task",
    sa.Column("id", sa.UUID(), primary_key=True),
    sa.Column("plan_id", sa.UUID(), sa.ForeignKey("sl_patient_instruction_plan.id", ondelete="CASCADE"), index=True),
    sa.Column("patient_id", sa.UUID(), sa.ForeignKey("sl_patient.id", ondelete="CASCADE"), index=True),
    sa.Column("plan_item_id", sa.String(100), nullable=False),  # ID within template content

    # Task identification
    sa.Column("task_type", sa.String(50), nullable=False),  # vital_sign, medication, activity, etc.
    sa.Column("task_code", sa.String(100), nullable=False),  # bp_reading, scheduled_dose, etc.
    sa.Column("title", sa.String(255), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),

    # Completion method
    sa.Column("completion_method", sa.String(20), nullable=False),  # auto, manual, hybrid
    sa.Column("data_trigger_types", sa.ARRAY(sa.String()), nullable=True),
    sa.Column("data_threshold", sa.JSON(), nullable=True),
    sa.Column("confirmation_prompt", sa.String(500), nullable=True),

    # Scheduling (stored in UTC)
    sa.Column("scheduled_date", sa.Date(), nullable=False, index=True),
    sa.Column("scheduled_at", sa.DateTime(), nullable=False),  # UTC
    sa.Column("scheduled_time_local", sa.String(10), nullable=True),  # "08:00" for display
    sa.Column("patient_timezone", sa.String(50), nullable=False),
    sa.Column("time_window_minutes", sa.Integer(), default=60),

    # Status
    sa.Column("status", sa.String(20), default="pending", index=True),  # pending, completed, skipped, missed, cancelled
    sa.Column("completed_at", sa.DateTime(), nullable=True),
    sa.Column("completion_source", sa.String(50), nullable=True),  # auto_data, user_confirmed, clinician_marked

    # Linked data (for auto-completed tasks)
    sa.Column("linked_data_type", sa.String(50), nullable=True),
    sa.Column("linked_data_id", sa.UUID(), nullable=True),
    sa.Column("linked_data_value", sa.String(255), nullable=True),  # "128/82 mmHg"

    # User feedback
    sa.Column("user_notes", sa.Text(), nullable=True),
    sa.Column("skip_reason", sa.String(255), nullable=True),

    # Notification tracking
    sa.Column("reminder_sent_at", sa.DateTime(), nullable=True),
    sa.Column("overdue_notification_count", sa.Integer(), default=0),
    sa.Column("last_overdue_sent_at", sa.DateTime(), nullable=True),
    sa.Column("confirmation_sent_at", sa.DateTime(), nullable=True),
    sa.Column("confirmation_response_count", sa.Integer(), default=0),

    # Audit
    sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),

    # Indexes for common queries
    sa.Index("ix_sl_patient_instruction_task_patient_date", "patient_id", "scheduled_date"),
    sa.Index("ix_sl_patient_instruction_task_status_date", "status", "scheduled_date"),
)
```

#### sl_task_notification_log
```python
op.create_table(
    "sl_task_notification_log",
    sa.Column("id", sa.UUID(), primary_key=True),
    sa.Column("task_id", sa.UUID(), sa.ForeignKey("sl_patient_instruction_task.id", ondelete="CASCADE"), index=True),
    sa.Column("patient_id", sa.UUID(), sa.ForeignKey("sl_patient.id", ondelete="CASCADE"), index=True),

    # Notification details
    sa.Column("notification_type", sa.String(50), nullable=False),  # reminder, overdue, confirmation, success
    sa.Column("channel", sa.String(20), nullable=False),  # push, sms, email

    # Timing
    sa.Column("sent_at", sa.DateTime(), nullable=False),
    sa.Column("delivered_at", sa.DateTime(), nullable=True),
    sa.Column("read_at", sa.DateTime(), nullable=True),

    # Response (for confirmation notifications)
    sa.Column("response", sa.String(20), nullable=True),  # yes, no, snooze
    sa.Column("responded_at", sa.DateTime(), nullable=True),

    # Content
    sa.Column("title", sa.String(255), nullable=False),
    sa.Column("body", sa.Text(), nullable=False),
    sa.Column("action_data", sa.JSON(), nullable=True),
)
```

#### Update sl_patient table
```python
# Add timezone column to existing patient table
op.add_column("sl_patient", sa.Column("timezone", sa.String(50), default="America/New_York"))
```

### 1.2 SQLAlchemy Models

**Files to create:**

| File | Models |
|------|--------|
| `backend/sense_loop/models/activity_template.py` | ActivityTemplate |
| `backend/sense_loop/models/instruction_template.py` | InstructionTemplate, InstructionTemplateHealthFocus |
| `backend/sense_loop/models/patient_instruction_plan.py` | PatientInstructionPlan |
| `backend/sense_loop/models/patient_instruction_task.py` | PatientInstructionTask |
| `backend/sense_loop/models/task_notification_log.py` | TaskNotificationLog |

**Update:**
- `backend/sense_loop/models/patient.py` - Add `timezone` field
- `backend/sense_loop/models/__init__.py` - Export new models

### 1.3 Seed Data

**File**: `backend/migrations/versions/YYYY_MM_DD_HHMM-seed_instruction_template_value_sets.py`

Seed ValueSets:

#### activity_category
```python
categories = [
    {"code": "wound-care", "display": "Wound Care"},
    {"code": "medications", "display": "Medications"},
    {"code": "activity", "display": "Activity & Exercise"},
    {"code": "diet", "display": "Diet & Nutrition"},
    {"code": "follow-up", "display": "Follow-up Care"},
    {"code": "warning-signs", "display": "Warning Signs"},
    {"code": "monitoring", "display": "Self-Monitoring"},
    {"code": "education", "display": "Patient Education"},
    {"code": "other", "display": "Other"},
]
```

#### health_focus
```python
health_focuses = [
    # Surgical
    {"code": "post-angioplasty", "display": "Post-Angioplasty Recovery", "category": "surgical"},
    {"code": "post-bypass", "display": "Post-Bypass Recovery", "category": "surgical"},
    {"code": "post-carotid-endarterectomy", "display": "Post-Carotid Endarterectomy", "category": "surgical"},
    {"code": "post-carotid-stenting", "display": "Post-Carotid Stenting", "category": "surgical"},
    {"code": "post-aneurysm-repair", "display": "Post-Aneurysm Repair", "category": "surgical"},
    {"code": "post-surgical-bypass", "display": "Post-Surgical Bypass", "category": "surgical"},
    {"code": "post-stent-graft", "display": "Post-Endovascular Stent Graft", "category": "surgical"},

    # Chronic conditions
    {"code": "hypertension", "display": "Hypertension Management", "category": "chronic"},
    {"code": "diabetes-type2", "display": "Type 2 Diabetes Management", "category": "chronic"},
    {"code": "heart-failure", "display": "Heart Failure Management", "category": "chronic"},
    {"code": "atrial-fibrillation", "display": "Atrial Fibrillation Management", "category": "chronic"},
    {"code": "hyperlipidemia", "display": "Hyperlipidemia Management", "category": "chronic"},

    # Preventive
    {"code": "cardiac-rehab", "display": "Cardiac Rehabilitation", "category": "preventive"},
    {"code": "weight-management", "display": "Weight Management", "category": "preventive"},
]
```

#### task_type
```python
task_types = [
    # Vital signs (auto-complete)
    {"code": "bp_reading", "display": "Blood Pressure Reading", "type": "vital_sign", "completion_method": "auto", "data_triggers": ["blood_pressure"]},
    {"code": "heart_rate_reading", "display": "Heart Rate Reading", "type": "vital_sign", "completion_method": "auto", "data_triggers": ["heart_rate"]},
    {"code": "spo2_reading", "display": "SpO2 Reading", "type": "vital_sign", "completion_method": "auto", "data_triggers": ["spo2"]},
    {"code": "weight_reading", "display": "Weight Reading", "type": "vital_sign", "completion_method": "auto", "data_triggers": ["weight"]},
    {"code": "temperature_reading", "display": "Temperature Reading", "type": "vital_sign", "completion_method": "auto", "data_triggers": ["temperature"]},
    {"code": "blood_glucose", "display": "Blood Glucose Reading", "type": "vital_sign", "completion_method": "auto", "data_triggers": ["blood_glucose"]},

    # Medications (manual)
    {"code": "scheduled_medication", "display": "Scheduled Medication", "type": "medication", "completion_method": "manual", "confirmation_prompt": "Did you take your {medication_name}?"},
    {"code": "prn_medication", "display": "As-Needed Medication", "type": "medication", "completion_method": "manual"},

    # Activity (hybrid)
    {"code": "exercise_session", "display": "Exercise Session", "type": "activity", "completion_method": "hybrid", "data_triggers": ["workout", "active_minutes"]},
    {"code": "walking_goal", "display": "Walking Goal", "type": "activity", "completion_method": "auto", "data_triggers": ["steps"]},
    {"code": "physical_therapy", "display": "Physical Therapy", "type": "activity", "completion_method": "manual"},

    # Wound care (manual)
    {"code": "wound_inspection", "display": "Wound Inspection", "type": "wound_care", "completion_method": "manual", "confirmation_prompt": "Did you check your incision site?"},
    {"code": "dressing_change", "display": "Dressing Change", "type": "wound_care", "completion_method": "manual", "confirmation_prompt": "Did you change your wound dressing?"},

    # Monitoring (auto via questionnaire)
    {"code": "symptom_check", "display": "Symptom Check-in", "type": "monitoring", "completion_method": "auto", "data_triggers": ["questionnaire_response"]},
    {"code": "pain_assessment", "display": "Pain Assessment", "type": "monitoring", "completion_method": "auto", "data_triggers": ["questionnaire_response"]},

    # Education (manual)
    {"code": "education_review", "display": "Review Educational Material", "type": "education", "completion_method": "manual"},

    # Follow-up (manual)
    {"code": "schedule_appointment", "display": "Schedule Follow-up Appointment", "type": "follow_up", "completion_method": "manual"},
]
```

### 1.4 Pydantic Schemas

**File**: `backend/sense_loop/schemas/instruction_template.py`

```python
# Request/Response schemas for:
# - ActivityTemplateCreate, ActivityTemplateUpdate, ActivityTemplateResponse
# - InstructionTemplateCreate, InstructionTemplateUpdate, InstructionTemplateResponse
# - PatientInstructionPlanCreate, PatientInstructionPlanUpdate, PatientInstructionPlanResponse
# - TimingConfig schema
# - ItemConfig schema
# - SectionConfig schema
```

**File**: `backend/sense_loop/schemas/patient_task.py`

```python
# Request/Response schemas for:
# - PatientTaskResponse, PatientTaskListResponse
# - TaskCompleteRequest, TaskSkipRequest, TaskSnoozeRequest
# - TaskConfirmationResponse
```

---

## Phase 2: Backend Services

### 2.1 Template Services

**File**: `backend/sense_loop/services/activity_template_service.py`

```python
class ActivityTemplateService:
    async def create(self, data: ActivityTemplateCreate, created_by: Practitioner) -> ActivityTemplate
    async def update(self, id: UUID, data: ActivityTemplateUpdate) -> ActivityTemplate
    async def get(self, id: UUID) -> ActivityTemplate | None
    async def list(self, org_id: UUID | None, include_shared: bool = True, status: str | None = None) -> list[ActivityTemplate]
    async def retire(self, id: UUID) -> ActivityTemplate
    async def duplicate(self, id: UUID, to_org_id: UUID | None) -> ActivityTemplate
```

**File**: `backend/sense_loop/services/instruction_template_service.py`

```python
class InstructionTemplateService:
    async def create(self, data: InstructionTemplateCreate, created_by: Practitioner) -> InstructionTemplate
    async def update(self, id: UUID, data: InstructionTemplateUpdate) -> InstructionTemplate
    async def get(self, id: UUID) -> InstructionTemplate | None
    async def get_with_resolved_activities(self, id: UUID) -> dict  # Resolves activity references
    async def list(self, org_id: UUID | None, health_focus: str | None = None) -> list[InstructionTemplate]
    async def retire(self, id: UUID) -> InstructionTemplate
    async def duplicate(self, id: UUID, to_org_id: UUID | None) -> InstructionTemplate
    async def preview(self, id: UUID) -> dict  # Full resolved preview
```

**File**: `backend/sense_loop/services/patient_instruction_plan_service.py`

```python
class PatientInstructionPlanService:
    async def assign(self, patient_id: UUID, template_id: UUID, assigned_by: Practitioner, customizations: dict | None = None) -> PatientInstructionPlan
    async def update(self, id: UUID, customizations: dict) -> PatientInstructionPlan
    async def cancel(self, id: UUID) -> PatientInstructionPlan
    async def complete(self, id: UUID) -> PatientInstructionPlan
    async def get_active_plans(self, patient_id: UUID) -> list[PatientInstructionPlan]
    async def get_resolved_content(self, id: UUID) -> dict  # Merged template + customizations

    def _resolve_content(self, template: InstructionTemplate, customizations: dict | None) -> dict
    def _merge_timing_override(self, base_timing: dict, override: dict) -> dict
```

### 2.2 Task Generation Service

**File**: `backend/sense_loop/services/task_generation_service.py`

```python
class TaskGenerationConfig:
    generation_window_days: int = 7
    default_time_window_minutes: int = 60

class TaskGenerationService:
    def __init__(self, db: AsyncSession, config: TaskGenerationConfig):
        self.db = db
        self.config = config

    async def generate_tasks_for_plan(
        self,
        plan: PatientInstructionPlan,
        through_date: date | None = None
    ) -> list[PatientInstructionTask]:
        """Generate tasks for a plan through the specified date."""

    async def ensure_tasks_generated(
        self,
        plan: PatientInstructionPlan,
        through_date: date | None = None
    ) -> int:
        """Ensure tasks exist through date, return count of new tasks."""

    async def regenerate_on_plan_change(
        self,
        plan: PatientInstructionPlan
    ) -> tuple[int, int]:
        """Cancel pending tasks and regenerate. Returns (cancelled, created)."""

    async def generate_daily_tasks(self) -> int:
        """Cron job: extend task window for all active plans. Returns count."""

    def _expand_timing(
        self,
        timing: dict,
        start_date: date,
        end_date: date,
        reference_date: date | None = None  # surgery_date, assignment_date, etc.
    ) -> list[date]:
        """Expand timing pattern into list of dates."""

    def _generate_task_datetime(
        self,
        patient_timezone: str,
        scheduled_date: date,
        time_of_day: str | None
    ) -> tuple[datetime, str | None]:
        """Generate UTC datetime and local time string."""

    def _get_task_type_config(self, item: dict) -> dict:
        """Get completion_method, data_triggers, etc. from item or activity."""
```

### 2.3 Task Completion Service

**File**: `backend/sense_loop/services/task_completion_service.py`

```python
class TaskCompletionService:
    def __init__(self, db: AsyncSession, notification_service: TaskNotificationService):
        self.db = db
        self.notification_service = notification_service

    async def on_data_received(
        self,
        patient_id: UUID,
        data_type: str,
        data_id: UUID,
        data_value: Any,
        timestamp: datetime
    ) -> list[PatientInstructionTask]:
        """
        Called when health data is received.
        Find and complete matching pending tasks.
        Returns list of completed tasks.
        """

    async def on_questionnaire_submitted(
        self,
        patient_id: UUID,
        questionnaire_code: str,
        response_id: UUID,
        submitted_at: datetime
    ) -> list[PatientInstructionTask]:
        """Called when questionnaire is submitted."""

    async def complete_task_manually(
        self,
        task_id: UUID,
        notes: str | None = None
    ) -> PatientInstructionTask:
        """User marks task as complete."""

    async def skip_task(
        self,
        task_id: UUID,
        reason: str | None = None
    ) -> PatientInstructionTask:
        """User skips a task."""

    async def snooze_task(
        self,
        task_id: UUID,
        snooze_minutes: int = 30
    ) -> PatientInstructionTask:
        """Snooze reminder for a task."""

    async def handle_confirmation_response(
        self,
        task_id: UUID,
        response: str,  # yes, no, snooze
        notes: str | None = None
    ) -> PatientInstructionTask:
        """Handle response to confirmation notification."""

    async def mark_overdue_tasks(self) -> int:
        """Cron job: mark tasks as missed after window expires. Returns count."""

    def _find_matching_tasks(
        self,
        patient_id: UUID,
        data_type: str,
        timestamp: datetime
    ) -> list[PatientInstructionTask]:
        """Find pending tasks that match this data type within time window."""

    def _is_within_time_window(
        self,
        task: PatientInstructionTask,
        timestamp: datetime
    ) -> bool:
        """Check if timestamp falls within task's acceptable window."""

    def _check_threshold(
        self,
        task: PatientInstructionTask,
        data_value: Any
    ) -> bool:
        """Check if data meets task's threshold (e.g., min_steps)."""

    def _format_data_value(
        self,
        data_type: str,
        data_value: Any
    ) -> str:
        """Format data value for display (e.g., '128/82 mmHg')."""
```

### 2.4 Task Notification Service

**File**: `backend/sense_loop/services/task_notification_service.py`

```python
class TaskNotificationConfig:
    # Reminder
    reminder_enabled: bool = True
    reminder_minutes_before: int = 15

    # Overdue
    overdue_enabled: bool = True
    overdue_minutes_after: int = 30
    overdue_max_retries: int = 2
    overdue_retry_interval_minutes: int = 60

    # Confirmation
    confirmation_enabled: bool = True
    confirmation_minutes_after: int = 30
    confirmation_max_retries: int = 2

    # Success
    success_notification_enabled: bool = True

    # Quiet hours
    quiet_hours_start: time = time(22, 0)
    quiet_hours_end: time = time(7, 0)

    # Daily summary
    daily_summary_enabled: bool = True
    daily_summary_time: time = time(7, 0)

class TaskNotificationService:
    def __init__(
        self,
        db: AsyncSession,
        push_service: PushNotificationService,
        config: TaskNotificationConfig
    ):
        self.db = db
        self.push_service = push_service
        self.config = config

    async def process_pending_notifications(self) -> dict:
        """
        Cron job: called every minute.
        Send due reminders, overdue alerts, confirmations.
        Returns counts by type.
        """

    async def send_reminder(self, task: PatientInstructionTask) -> bool:
        """Send pre-task reminder. Returns success."""

    async def send_overdue(self, task: PatientInstructionTask) -> bool:
        """Send overdue notification."""

    async def send_confirmation(self, task: PatientInstructionTask) -> bool:
        """Send confirmation request with quick actions."""

    async def send_success(
        self,
        task: PatientInstructionTask,
        data_value: str
    ) -> bool:
        """Send completion acknowledgment."""

    async def send_daily_summary(self, patient_id: UUID) -> bool:
        """Send morning summary of today's tasks."""

    def _is_quiet_hours(self, patient_timezone: str) -> bool:
        """Check if current time is in quiet hours for patient's timezone."""

    def _get_tasks_needing_reminder(self, now: datetime) -> list[PatientInstructionTask]:
        """Find tasks that need reminder sent."""

    def _get_overdue_tasks(self, now: datetime) -> list[PatientInstructionTask]:
        """Find tasks that are overdue and need notification."""

    def _get_tasks_needing_confirmation(self, now: datetime) -> list[PatientInstructionTask]:
        """Find manual tasks past their time that need confirmation."""

    def _format_reminder_message(self, task: PatientInstructionTask) -> tuple[str, str]:
        """Generate title and body for reminder."""

    def _format_confirmation_message(self, task: PatientInstructionTask) -> tuple[str, str]:
        """Generate title and body for confirmation."""

    async def _log_notification(
        self,
        task: PatientInstructionTask,
        notification_type: str,
        channel: str,
        title: str,
        body: str,
        action_data: dict | None = None
    ) -> TaskNotificationLog:
        """Log notification to database."""
```

### 2.5 FHIR Transformation Service

**File**: `backend/sense_loop/services/fhir_transformer.py`

```python
class FHIRTransformer:
    """Bidirectional transformation between internal models and FHIR resources."""

    # Export to FHIR
    def activity_to_fhir(self, activity: ActivityTemplate) -> dict:
        """Convert ActivityTemplate → FHIR ActivityDefinition"""

    def template_to_fhir(self, template: InstructionTemplate) -> dict:
        """Convert InstructionTemplate → FHIR PlanDefinition"""

    def plan_to_fhir(self, plan: PatientInstructionPlan, patient: Patient) -> dict:
        """Convert PatientInstructionPlan → FHIR CarePlan"""

    def timing_to_fhir(self, timing: dict) -> dict:
        """Convert internal timing → FHIR Timing"""

    # Import from FHIR
    def fhir_to_activity(self, resource: dict) -> ActivityTemplate:
        """Convert FHIR ActivityDefinition → ActivityTemplate"""

    def fhir_to_template(self, resource: dict) -> InstructionTemplate:
        """Convert FHIR PlanDefinition → InstructionTemplate"""

    def fhir_timing_to_internal(self, timing: dict) -> dict:
        """Convert FHIR Timing → internal timing"""

    # Helpers
    def _map_kind_to_fhir(self, kind: str) -> str:
        """Map internal kind to FHIR ActivityDefinition.kind"""

    def _build_codeable_concept(self, system: str | None, code: str | None) -> dict | None:
        """Build FHIR CodeableConcept from system and code"""
```

### 2.6 Integration Hooks

**File**: `backend/sense_loop/services/data_ingestion_hooks.py`

```python
class DataIngestionHooks:
    """Hooks into data ingestion pipeline for task completion."""

    def __init__(self, task_completion_service: TaskCompletionService):
        self.task_completion_service = task_completion_service

    async def on_vital_sign_received(
        self,
        patient_id: UUID,
        vital_type: str,
        data_point_id: UUID,
        value: dict,
        timestamp: datetime
    ):
        """Called when vital sign data is received from wearable/device."""
        await self.task_completion_service.on_data_received(
            patient_id=patient_id,
            data_type=vital_type,
            data_id=data_point_id,
            data_value=value,
            timestamp=timestamp
        )
```

Update existing data processing to call hooks:
- `backend/sense_loop/services/vital_processing_service.py` (if exists)
- Or add to relevant data ingestion endpoints

---

## Phase 3: API Endpoints

### 3.1 Activity Template Routes

**File**: `backend/sense_loop/api/routes/activity_templates.py`

```python
router = APIRouter(prefix="/activity-templates", tags=["Activity Templates"])

@router.get("/")
async def list_activity_templates(
    status: str | None = None,
    category: str | None = None,
    include_shared: bool = True,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db)
) -> list[ActivityTemplateResponse]:
    """List activity templates (org + shared)."""

@router.post("/")
async def create_activity_template(
    data: ActivityTemplateCreate,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db)
) -> ActivityTemplateResponse:
    """Create a new activity template."""

@router.get("/{id}")
async def get_activity_template(
    id: UUID,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db)
) -> ActivityTemplateResponse:
    """Get activity template by ID."""

@router.put("/{id}")
async def update_activity_template(
    id: UUID,
    data: ActivityTemplateUpdate,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db)
) -> ActivityTemplateResponse:
    """Update activity template."""

@router.post("/{id}/retire")
async def retire_activity_template(
    id: UUID,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db)
) -> ActivityTemplateResponse:
    """Retire (soft delete) activity template."""

@router.post("/{id}/duplicate")
async def duplicate_activity_template(
    id: UUID,
    to_shared: bool = False,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db)
) -> ActivityTemplateResponse:
    """Duplicate activity template."""
```

### 3.2 Instruction Template Routes

**File**: `backend/sense_loop/api/routes/instruction_templates.py`

```python
router = APIRouter(prefix="/instruction-templates", tags=["Instruction Templates"])

@router.get("/")
async def list_instruction_templates(
    status: str | None = None,
    health_focus: str | None = None,
    include_shared: bool = True,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db)
) -> list[InstructionTemplateResponse]:
    """List instruction templates."""

@router.post("/")
async def create_instruction_template(
    data: InstructionTemplateCreate,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db)
) -> InstructionTemplateResponse:
    """Create instruction template."""

@router.get("/{id}")
async def get_instruction_template(
    id: UUID,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db)
) -> InstructionTemplateResponse:
    """Get instruction template."""

@router.put("/{id}")
async def update_instruction_template(
    id: UUID,
    data: InstructionTemplateUpdate,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db)
) -> InstructionTemplateResponse:
    """Update instruction template."""

@router.get("/{id}/preview")
async def preview_instruction_template(
    id: UUID,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db)
) -> InstructionTemplatePreviewResponse:
    """Get fully resolved preview of template."""

@router.post("/{id}/duplicate")
async def duplicate_instruction_template(
    id: UUID,
    to_shared: bool = False,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db)
) -> InstructionTemplateResponse:
    """Duplicate instruction template."""
```

### 3.3 Patient Instruction Plan Routes

**File**: `backend/sense_loop/api/routes/patient_instruction_plans.py`

```python
router = APIRouter(prefix="/patients/{patient_id}/instruction-plans", tags=["Patient Instruction Plans"])

@router.get("/")
async def list_patient_instruction_plans(
    patient_id: UUID,
    status: str | None = None,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db)
) -> list[PatientInstructionPlanResponse]:
    """List patient's instruction plans."""

@router.post("/")
async def assign_instruction_plan(
    patient_id: UUID,
    data: PatientInstructionPlanCreate,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db)
) -> PatientInstructionPlanResponse:
    """Assign instruction template to patient."""

@router.get("/{plan_id}")
async def get_patient_instruction_plan(
    patient_id: UUID,
    plan_id: UUID,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db)
) -> PatientInstructionPlanResponse:
    """Get patient's instruction plan."""

@router.put("/{plan_id}")
async def update_patient_instruction_plan(
    patient_id: UUID,
    plan_id: UUID,
    data: PatientInstructionPlanUpdate,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db)
) -> PatientInstructionPlanResponse:
    """Update patient's instruction plan customizations."""

@router.post("/{plan_id}/cancel")
async def cancel_patient_instruction_plan(
    patient_id: UUID,
    plan_id: UUID,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db)
) -> PatientInstructionPlanResponse:
    """Cancel patient's instruction plan."""

@router.get("/{plan_id}/tasks")
async def list_plan_tasks(
    patient_id: UUID,
    plan_id: UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
    practitioner: Practitioner = Depends(get_current_practitioner),
    db: AsyncSession = Depends(get_db)
) -> list[PatientTaskResponse]:
    """List tasks for a specific plan."""
```

### 3.4 Mobile API Routes

**File**: `backend/sense_loop/api/routes/mobile.py` (update existing)

Add new endpoints:

```python
@router.post("/tasks/today")
async def get_today_tasks(
    request: MobileTasksRequest,
    patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db)
) -> MobileTasksResponse:
    """Get today's tasks for patient."""

@router.post("/tasks/{task_id}/complete")
async def complete_task(
    task_id: UUID,
    request: TaskCompleteRequest,
    patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db)
) -> TaskResponse:
    """Mark task as complete (manual)."""

@router.post("/tasks/{task_id}/skip")
async def skip_task(
    task_id: UUID,
    request: TaskSkipRequest,
    patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db)
) -> TaskResponse:
    """Skip a task."""

@router.post("/tasks/{task_id}/snooze")
async def snooze_task(
    task_id: UUID,
    request: TaskSnoozeRequest,
    patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db)
) -> TaskResponse:
    """Snooze task reminder."""

@router.post("/tasks/confirm")
async def handle_task_confirmation(
    request: TaskConfirmationRequest,
    patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db)
) -> TaskResponse:
    """Handle response to confirmation notification."""

@router.post("/instructions")
async def get_patient_instructions(
    request: MobileInstructionsRequest,
    patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db)
) -> MobileInstructionsResponse:
    """Get patient's active instruction plans with resolved content."""
```

### 3.5 Register Routes

**File**: `backend/sense_loop/api/routes/__init__.py` (update)

```python
from .activity_templates import router as activity_templates_router
from .instruction_templates import router as instruction_templates_router
from .patient_instruction_plans import router as patient_instruction_plans_router

# Add to main router
api_router.include_router(activity_templates_router)
api_router.include_router(instruction_templates_router)
api_router.include_router(patient_instruction_plans_router)
```

---

## Phase 4: Frontend Implementation

### 4.1 API Client & Hooks

**File**: `frontend/src/lib/api/services/instruction-template.service.ts`

```typescript
export const instructionTemplateService = {
  // Activity Templates
  listActivityTemplates: (params?: ActivityTemplateListParams) => Promise<ActivityTemplate[]>,
  createActivityTemplate: (data: ActivityTemplateCreate) => Promise<ActivityTemplate>,
  updateActivityTemplate: (id: string, data: ActivityTemplateUpdate) => Promise<ActivityTemplate>,
  getActivityTemplate: (id: string) => Promise<ActivityTemplate>,
  retireActivityTemplate: (id: string) => Promise<ActivityTemplate>,
  duplicateActivityTemplate: (id: string, toShared?: boolean) => Promise<ActivityTemplate>,

  // Instruction Templates
  listInstructionTemplates: (params?: InstructionTemplateListParams) => Promise<InstructionTemplate[]>,
  createInstructionTemplate: (data: InstructionTemplateCreate) => Promise<InstructionTemplate>,
  updateInstructionTemplate: (id: string, data: InstructionTemplateUpdate) => Promise<InstructionTemplate>,
  getInstructionTemplate: (id: string) => Promise<InstructionTemplate>,
  previewInstructionTemplate: (id: string) => Promise<InstructionTemplatePreview>,

  // Patient Plans
  listPatientPlans: (patientId: string) => Promise<PatientInstructionPlan[]>,
  assignPlan: (patientId: string, data: AssignPlanRequest) => Promise<PatientInstructionPlan>,
  updatePlan: (patientId: string, planId: string, data: UpdatePlanRequest) => Promise<PatientInstructionPlan>,
  cancelPlan: (patientId: string, planId: string) => Promise<PatientInstructionPlan>,
};
```

**File**: `frontend/src/lib/api/types/instruction-template.ts`

```typescript
// Type definitions for all template-related types
```

**File**: `frontend/src/hooks/api/use-instruction-templates.ts`

```typescript
// React Query hooks for template operations
export function useActivityTemplates(params?: ActivityTemplateListParams)
export function useActivityTemplate(id: string)
export function useCreateActivityTemplate()
export function useUpdateActivityTemplate()

export function useInstructionTemplates(params?: InstructionTemplateListParams)
export function useInstructionTemplate(id: string)
export function useCreateInstructionTemplate()
export function useUpdateInstructionTemplate()

export function usePatientInstructionPlans(patientId: string)
export function useAssignInstructionPlan()
```

### 4.2 UI Components

**Directory**: `frontend/src/components/sl/templates/`

| Component | Description |
|-----------|-------------|
| `ActivityTemplateForm.tsx` | Form for creating/editing activity templates |
| `ActivityTemplateList.tsx` | List of activity templates with filters |
| `ActivityLibraryModal.tsx` | Modal for browsing and selecting activities |
| `InstructionTemplateForm.tsx` | Form for template metadata |
| `InstructionBuilder.tsx` | Visual builder for sections and items |
| `SectionEditor.tsx` | Editor for a single section |
| `ItemEditor.tsx` | Editor for a single item (inline or activity ref) |
| `TimingEditor.tsx` | Component for timing configuration |
| `InstructionTemplateList.tsx` | List of instruction templates |
| `InstructionPreview.tsx` | Preview of resolved template |
| `PatientPlanAssignment.tsx` | Component for assigning template to patient |
| `PatientPlanCustomizer.tsx` | UI for customizing assigned plan |
| `HealthFocusSelect.tsx` | Multi-select for health focus codes |
| `CategoryBadge.tsx` | Colored badge for activity category |
| `StatusBadge.tsx` | Badge for template status |

### 4.3 Pages/Routes

**Directory**: `frontend/src/routes/sl/_sl-authenticated/templates/`

| Route | Component | Description |
|-------|-----------|-------------|
| `/templates` | `index.tsx` | Templates landing page (tabs for activities/instructions) |
| `/templates/activities` | `activities/index.tsx` | Activity template list |
| `/templates/activities/new` | `activities/new.tsx` | Create activity template |
| `/templates/activities/$id` | `activities/$id.tsx` | Edit activity template |
| `/templates/instructions` | `instructions/index.tsx` | Instruction template list |
| `/templates/instructions/new` | `instructions/new.tsx` | Create instruction template |
| `/templates/instructions/$id` | `instructions/$id.tsx` | Edit instruction template |
| `/templates/instructions/$id/preview` | `instructions/$id.preview.tsx` | Preview instruction template |

**Update existing routes:**

| Route | Update |
|-------|--------|
| `/patients/$patientId` | Add "Instruction Plans" tab with assignment UI |

### 4.4 Component Details

#### TimingEditor Component

```tsx
interface TimingEditorProps {
  value: TimingConfig | null;
  onChange: (timing: TimingConfig | null) => void;
  showDuration?: boolean;  // Show bounds configuration
  showRelative?: boolean;  // Show relative start options
}

// Presets:
// - Once daily
// - Twice daily (8 AM, 8 PM)
// - Three times daily
// - Every X hours
// - Weekly
// - Custom

// Duration options:
// - For X days
// - Until specific date
// - Ongoing (no end)

// Relative start options:
// - Day of surgery
// - Day X post-surgery
// - On assignment date
// - Specific date
```

#### InstructionBuilder Component

```tsx
interface InstructionBuilderProps {
  value: InstructionContent;
  activities: ActivityTemplate[];
  onChange: (content: InstructionContent) => void;
}

// Features:
// - Drag-and-drop sections
// - Add section button
// - Within each section:
//   - Drag-and-drop items
//   - Add from activity library
//   - Add inline item
//   - Configure timing per item
//   - Set priority (routine/urgent)
// - Section actions: edit, delete, move up/down
// - Item actions: edit, delete, move
```

---

## Phase 5: Background Jobs & Integration

### 5.1 Scheduled Jobs

**File**: `backend/sense_loop/jobs/task_jobs.py`

```python
# Job 1: Generate daily tasks (run at 2 AM)
async def generate_daily_tasks():
    """Extend task window for all active plans."""
    service = TaskGenerationService(db)
    count = await service.generate_daily_tasks()
    logger.info(f"Generated {count} tasks for next day")

# Job 2: Process notifications (run every minute)
async def process_task_notifications():
    """Send due reminders, overdue alerts, confirmations."""
    service = TaskNotificationService(db, push_service)
    counts = await service.process_pending_notifications()
    logger.info(f"Sent notifications: {counts}")

# Job 3: Mark overdue tasks (run every 15 minutes)
async def mark_overdue_tasks():
    """Mark tasks as missed after window expires."""
    service = TaskCompletionService(db, notification_service)
    count = await service.mark_overdue_tasks()
    logger.info(f"Marked {count} tasks as missed")

# Job 4: Send daily summaries (run at 7 AM per timezone)
async def send_daily_summaries():
    """Send morning task summary to patients."""
    # Group patients by timezone, send at 7 AM local
    ...
```

**File**: `backend/sense_loop/jobs/scheduler.py`

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# Register jobs
scheduler.add_job(generate_daily_tasks, 'cron', hour=2, minute=0)
scheduler.add_job(process_task_notifications, 'interval', minutes=1)
scheduler.add_job(mark_overdue_tasks, 'interval', minutes=15)
scheduler.add_job(send_daily_summaries, 'cron', hour=7, minute=0)
```

### 5.2 Data Ingestion Integration

Identify where health data enters the system and add hooks:

```python
# In existing data processing (e.g., when BP data arrives)
async def process_vital_sign_data(patient_id: UUID, data: VitalSignData):
    # Existing processing...

    # NEW: Check for task completion
    hooks = DataIngestionHooks(task_completion_service)
    await hooks.on_vital_sign_received(
        patient_id=patient_id,
        vital_type=data.type,
        data_point_id=data.id,
        value=data.value,
        timestamp=data.timestamp
    )
```

---

## Testing Strategy

### Unit Tests

| Area | Tests |
|------|-------|
| Models | Validation, relationships, defaults |
| Timing expansion | `_expand_timing()` with various patterns |
| Task matching | `_find_matching_tasks()` logic |
| Time window | `_is_within_time_window()` edge cases |
| Threshold checking | `_check_threshold()` for various thresholds |
| FHIR transformation | Round-trip conversion accuracy |
| Content resolution | Template + customization merging |

### Integration Tests

| Area | Tests |
|------|-------|
| Template CRUD | Create, update, list, retire, duplicate |
| Plan assignment | Assign template, generate tasks |
| Task completion | Auto-complete on data, manual complete |
| Notifications | Reminder, overdue, confirmation flow |
| Mobile API | Tasks today, complete, skip, snooze |

### E2E Tests

| Flow | Steps |
|------|-------|
| Template creation | Create activity → create template → assign to patient |
| Task lifecycle | Task generated → reminder sent → data received → auto-complete |
| Manual task | Task generated → confirmation sent → user confirms → complete |
| Plan modification | Modify plan → tasks regenerated |

---

## File Summary

### New Files (Backend)

| File | Purpose |
|------|---------|
| `migrations/..._add_instruction_template_tables.py` | Database tables |
| `migrations/..._seed_instruction_template_value_sets.py` | Seed data |
| `models/activity_template.py` | ActivityTemplate model |
| `models/instruction_template.py` | InstructionTemplate model |
| `models/patient_instruction_plan.py` | PatientInstructionPlan model |
| `models/patient_instruction_task.py` | PatientInstructionTask model |
| `models/task_notification_log.py` | TaskNotificationLog model |
| `schemas/instruction_template.py` | Request/response schemas |
| `schemas/patient_task.py` | Task schemas |
| `services/activity_template_service.py` | Activity template service |
| `services/instruction_template_service.py` | Instruction template service |
| `services/patient_instruction_plan_service.py` | Plan service |
| `services/task_generation_service.py` | Task generation |
| `services/task_completion_service.py` | Task completion |
| `services/task_notification_service.py` | Notifications |
| `services/fhir_transformer.py` | FHIR conversion |
| `services/data_ingestion_hooks.py` | Data hooks |
| `api/routes/activity_templates.py` | Activity API |
| `api/routes/instruction_templates.py` | Template API |
| `api/routes/patient_instruction_plans.py` | Plan API |
| `jobs/task_jobs.py` | Background jobs |
| `jobs/scheduler.py` | Job scheduler |

### New Files (Frontend)

| File | Purpose |
|------|---------|
| `lib/api/services/instruction-template.service.ts` | API client |
| `lib/api/types/instruction-template.ts` | TypeScript types |
| `hooks/api/use-instruction-templates.ts` | React Query hooks |
| `components/sl/templates/ActivityTemplateForm.tsx` | Activity form |
| `components/sl/templates/ActivityTemplateList.tsx` | Activity list |
| `components/sl/templates/ActivityLibraryModal.tsx` | Activity picker |
| `components/sl/templates/InstructionTemplateForm.tsx` | Template form |
| `components/sl/templates/InstructionBuilder.tsx` | Visual builder |
| `components/sl/templates/SectionEditor.tsx` | Section editor |
| `components/sl/templates/ItemEditor.tsx` | Item editor |
| `components/sl/templates/TimingEditor.tsx` | Timing config |
| `components/sl/templates/InstructionTemplateList.tsx` | Template list |
| `components/sl/templates/InstructionPreview.tsx` | Preview |
| `components/sl/templates/PatientPlanAssignment.tsx` | Assignment UI |
| `routes/sl/_sl-authenticated/templates/index.tsx` | Templates page |
| `routes/sl/_sl-authenticated/templates/activities/` | Activity routes |
| `routes/sl/_sl-authenticated/templates/instructions/` | Template routes |

### Updated Files

| File | Changes |
|------|---------|
| `models/__init__.py` | Export new models |
| `models/patient.py` | Add timezone field |
| `api/routes/__init__.py` | Register new routers |
| `api/routes/mobile.py` | Add task endpoints |

---

## Implementation Order

### Week 1: Foundation
1. Create database migrations
2. Create SQLAlchemy models
3. Create Pydantic schemas
4. Seed ValueSets

### Week 2: Core Services
5. Implement ActivityTemplateService
6. Implement InstructionTemplateService
7. Implement PatientInstructionPlanService
8. Implement content resolution logic

### Week 3: Task System
9. Implement TaskGenerationService
10. Implement TaskCompletionService
11. Implement TaskNotificationService
12. Implement data ingestion hooks

### Week 4: API & Jobs
13. Create API routes (activity, instruction, plan)
14. Update mobile API routes
15. Implement background jobs
16. Integration testing

### Week 5: Frontend - Templates
17. Create API client and hooks
18. Build TimingEditor component
19. Build ActivityTemplateForm and list
20. Build ActivityLibraryModal

### Week 6: Frontend - Builder
21. Build InstructionBuilder component
22. Build SectionEditor and ItemEditor
23. Build InstructionTemplateForm and list
24. Build InstructionPreview

### Week 7: Frontend - Patient
25. Build PatientPlanAssignment component
26. Update patient detail page
27. Build task list view (if clinician-facing)
28. E2E testing

### Week 8: Polish & Deploy
29. Error handling and edge cases
30. Performance optimization
31. Documentation
32. Deploy to staging
