"""Seed instruction template value sets

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7

"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Activity categories for classifying activity templates
ACTIVITY_CATEGORIES = [
    {"code": "wound-care", "display": "Wound Care", "description": "Instructions for wound and incision care"},
    {"code": "medications", "display": "Medications", "description": "Medication schedules and reminders"},
    {"code": "activity", "display": "Activity & Exercise", "description": "Physical activity and exercise instructions"},
    {"code": "diet", "display": "Diet & Nutrition", "description": "Dietary guidelines and nutrition advice"},
    {"code": "follow-up", "display": "Follow-up Care", "description": "Appointments and follow-up care instructions"},
    {"code": "warning-signs", "display": "Warning Signs", "description": "Symptoms to watch for and when to seek help"},
    {"code": "monitoring", "display": "Self-Monitoring", "description": "Vital signs and health metric monitoring"},
    {"code": "education", "display": "Patient Education", "description": "Educational materials and information"},
    {"code": "other", "display": "Other", "description": "Other care instructions"},
]

# Health focus codes for associating templates with conditions/procedures
HEALTH_FOCUSES = [
    # Surgical - Vascular
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
    {"code": "coronary-artery-disease", "display": "Coronary Artery Disease Management", "category": "chronic"},

    # Preventive / Rehabilitation
    {"code": "cardiac-rehab", "display": "Cardiac Rehabilitation", "category": "preventive"},
    {"code": "weight-management", "display": "Weight Management", "category": "preventive"},
    {"code": "smoking-cessation", "display": "Smoking Cessation", "category": "preventive"},
]

# Task types for classifying instruction tasks
TASK_TYPES = [
    # Vital signs (auto-complete from device data)
    {
        "code": "bp_reading",
        "display": "Blood Pressure Reading",
        "task_type": "vital_sign",
        "completion_method": "auto",
        "data_triggers": "blood_pressure",
    },
    {
        "code": "heart_rate_reading",
        "display": "Heart Rate Reading",
        "task_type": "vital_sign",
        "completion_method": "auto",
        "data_triggers": "heart_rate,resting_heart_rate",
    },
    {
        "code": "spo2_reading",
        "display": "SpO2 Reading",
        "task_type": "vital_sign",
        "completion_method": "auto",
        "data_triggers": "spo2,oxygen_saturation",
    },
    {
        "code": "weight_reading",
        "display": "Weight Reading",
        "task_type": "vital_sign",
        "completion_method": "auto",
        "data_triggers": "weight,body_mass",
    },
    {
        "code": "temperature_reading",
        "display": "Temperature Reading",
        "task_type": "vital_sign",
        "completion_method": "auto",
        "data_triggers": "temperature,body_temperature",
    },
    {
        "code": "blood_glucose",
        "display": "Blood Glucose Reading",
        "task_type": "vital_sign",
        "completion_method": "auto",
        "data_triggers": "blood_glucose,glucose",
    },

    # Medications (manual confirmation)
    {
        "code": "scheduled_medication",
        "display": "Scheduled Medication",
        "task_type": "medication",
        "completion_method": "manual",
        "confirmation_prompt": "Did you take your medication?",
    },
    {
        "code": "prn_medication",
        "display": "As-Needed Medication",
        "task_type": "medication",
        "completion_method": "manual",
        "confirmation_prompt": "Did you take your as-needed medication?",
    },

    # Activity (hybrid - detect but may need confirmation)
    {
        "code": "exercise_session",
        "display": "Exercise Session",
        "task_type": "activity",
        "completion_method": "hybrid",
        "data_triggers": "workout,active_minutes",
        "confirmation_prompt": "Did you complete your exercise session?",
    },
    {
        "code": "walking_goal",
        "display": "Walking Goal",
        "task_type": "activity",
        "completion_method": "auto",
        "data_triggers": "steps,walking_distance",
    },
    {
        "code": "physical_therapy",
        "display": "Physical Therapy Exercises",
        "task_type": "activity",
        "completion_method": "manual",
        "confirmation_prompt": "Did you complete your physical therapy exercises?",
    },

    # Wound care (manual)
    {
        "code": "wound_inspection",
        "display": "Wound Inspection",
        "task_type": "wound_care",
        "completion_method": "manual",
        "confirmation_prompt": "Did you inspect your incision site?",
    },
    {
        "code": "dressing_change",
        "display": "Dressing Change",
        "task_type": "wound_care",
        "completion_method": "manual",
        "confirmation_prompt": "Did you change your wound dressing?",
    },

    # Monitoring (auto via questionnaire)
    {
        "code": "symptom_check",
        "display": "Symptom Check-in",
        "task_type": "monitoring",
        "completion_method": "auto",
        "data_triggers": "questionnaire_response",
    },
    {
        "code": "pain_assessment",
        "display": "Pain Assessment",
        "task_type": "monitoring",
        "completion_method": "auto",
        "data_triggers": "questionnaire_response",
    },

    # Education (manual)
    {
        "code": "education_review",
        "display": "Review Educational Material",
        "task_type": "education",
        "completion_method": "manual",
        "confirmation_prompt": "Did you review the educational material?",
    },

    # Follow-up (manual)
    {
        "code": "schedule_appointment",
        "display": "Schedule Follow-up Appointment",
        "task_type": "follow_up",
        "completion_method": "manual",
        "confirmation_prompt": "Did you schedule your follow-up appointment?",
    },
]


def upgrade() -> None:
    # Insert activity_category ValueSet (organization_id = NULL for system-wide)
    activity_category_id = uuid4()
    op.execute(
        sa.text("""
            INSERT INTO sl_value_set (id, code, name, description, organization_id, is_active, created_at)
            VALUES (:id, :code, :name, :description, NULL, true, now())
        """).bindparams(
            id=activity_category_id,
            code="activity_category",
            name="Activity Category",
            description="Categories for classifying activity templates in instruction plans"
        )
    )

    # Insert activity category items
    import json
    for i, cat in enumerate(ACTIVITY_CATEGORIES):
        op.execute(
            sa.text("""
                INSERT INTO sl_value_set_item (id, value_set_id, code, display, extra_data, sort_order, is_active, created_at)
                VALUES (:id, :value_set_id, :code, :display, CAST(:extra_data AS jsonb), :sort_order, true, now())
            """).bindparams(
                id=uuid4(),
                value_set_id=activity_category_id,
                code=cat["code"],
                display=cat["display"],
                extra_data=json.dumps({"description": cat["description"]}),
                sort_order=i
            )
        )

    # Insert health_focus ValueSet (organization_id = NULL for system-wide)
    health_focus_id = uuid4()
    op.execute(
        sa.text("""
            INSERT INTO sl_value_set (id, code, name, description, organization_id, is_active, created_at)
            VALUES (:id, :code, :name, :description, NULL, true, now())
        """).bindparams(
            id=health_focus_id,
            code="health_focus",
            name="Health Focus",
            description="Health conditions and procedures for associating instruction templates"
        )
    )

    # Insert health focus items
    for i, focus in enumerate(HEALTH_FOCUSES):
        op.execute(
            sa.text("""
                INSERT INTO sl_value_set_item (id, value_set_id, code, display, extra_data, sort_order, is_active, created_at)
                VALUES (:id, :value_set_id, :code, :display, CAST(:extra_data AS jsonb), :sort_order, true, now())
            """).bindparams(
                id=uuid4(),
                value_set_id=health_focus_id,
                code=focus["code"],
                display=focus["display"],
                extra_data=json.dumps({"category": focus["category"]}),
                sort_order=i
            )
        )

    # Insert task_type ValueSet (organization_id = NULL for system-wide)
    task_type_id = uuid4()
    op.execute(
        sa.text("""
            INSERT INTO sl_value_set (id, code, name, description, organization_id, is_active, created_at)
            VALUES (:id, :code, :name, :description, NULL, true, now())
        """).bindparams(
            id=task_type_id,
            code="task_type",
            name="Task Type",
            description="Types of instruction tasks with completion method configuration"
        )
    )

    # Insert task type items
    for i, task in enumerate(TASK_TYPES):
        extra_obj = {
            "task_type": task["task_type"],
            "completion_method": task["completion_method"],
        }
        if "data_triggers" in task:
            extra_obj["data_triggers"] = task["data_triggers"]
        if "confirmation_prompt" in task:
            extra_obj["confirmation_prompt"] = task["confirmation_prompt"]

        op.execute(
            sa.text("""
                INSERT INTO sl_value_set_item (id, value_set_id, code, display, extra_data, sort_order, is_active, created_at)
                VALUES (:id, :value_set_id, :code, :display, CAST(:extra_data AS jsonb), :sort_order, true, now())
            """).bindparams(
                id=uuid4(),
                value_set_id=task_type_id,
                code=task["code"],
                display=task["display"],
                extra_data=json.dumps(extra_obj),
                sort_order=i
            )
        )


def downgrade() -> None:
    # Delete task_type ValueSet and items
    op.execute(
        sa.text("""
            DELETE FROM sl_value_set_item WHERE value_set_id IN (
                SELECT id FROM sl_value_set WHERE code = 'task_type'
            )
        """)
    )
    op.execute(
        sa.text("DELETE FROM sl_value_set WHERE code = 'task_type'")
    )

    # Delete health_focus ValueSet and items
    op.execute(
        sa.text("""
            DELETE FROM sl_value_set_item WHERE value_set_id IN (
                SELECT id FROM sl_value_set WHERE code = 'health_focus'
            )
        """)
    )
    op.execute(
        sa.text("DELETE FROM sl_value_set WHERE code = 'health_focus'")
    )

    # Delete activity_category ValueSet and items
    op.execute(
        sa.text("""
            DELETE FROM sl_value_set_item WHERE value_set_id IN (
                SELECT id FROM sl_value_set WHERE code = 'activity_category'
            )
        """)
    )
    op.execute(
        sa.text("DELETE FROM sl_value_set WHERE code = 'activity_category'")
    )
