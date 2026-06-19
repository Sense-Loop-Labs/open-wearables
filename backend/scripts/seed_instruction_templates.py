#!/usr/bin/env python3
"""Seed instruction templates and activity templates for Sense Loop.

This creates a sample Hypertension Management Plan with associated activity templates.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from uuid import UUID

from sqlalchemy import select

from app.database import SessionLocal
from sense_loop.models import ActivityTemplate, InstructionTemplate


# Activity templates - these are reusable task definitions
ACTIVITY_TEMPLATES = [
    {
        "id": UUID("7769a5bb-0967-443a-9411-c4d47e53c978"),
        "name": "blood-pressure-check",
        "title": "Blood Pressure Check",
        "description": "Measure and record your blood pressure",
        "status": "active",
        "version": "1.0.0",
        "category_code": "monitoring",
        "kind": "task",
        "completion_method": "auto",
        "data_trigger_types": ["blood_pressure"],
        "confirmation_prompt": None,
        "content": {},
        "default_timing": {
            "period": 1,
            "frequency": 3,
            "timeOfDay": ["09:00", "12:00", "16:00"],
            "periodUnit": "d",
            "windowMinutes": 60,
        },
    },
    {
        "id": UUID("3b4b472e-388b-4cc9-9c14-19155adc21b6"),
        "name": "30-minute-walk",
        "title": "30-Minute Walk",
        "description": "Please try to get a 30-minute walk in each day",
        "status": "active",
        "version": "1.0.0",
        "category_code": "activity",
        "kind": "task",
        "completion_method": "hybrid",
        "data_trigger_types": ["steps", "workout"],
        "confirmation_prompt": "Did you complete your exercise today?",
        "content": {},
        "default_timing": {
            "period": 1,
            "frequency": 1,
            "timeOfDay": ["12:00"],
            "periodUnit": "d",
        },
    },
    {
        "id": UUID("42519e56-3f2e-4228-8d4d-3937f82e8c90"),
        "name": "blood-pressure-medication",
        "title": "Blood Pressure Medication",
        "description": "Take your medication once daily",
        "status": "active",
        "version": "1.0.0",
        "category_code": "medications",
        "kind": "task",
        "completion_method": "manual",
        "data_trigger_types": None,
        "confirmation_prompt": "Did you take your blood pressure medication today?",
        "content": {},
        "default_timing": {
            "period": 1,
            "frequency": 1,
            "timeOfDay": ["08:00"],
            "periodUnit": "d",
            "windowMinutes": 60,
        },
    },
    {
        "id": UUID("9517cd87-5151-478c-aed8-84c6d525283a"),
        "name": "healthy-diet",
        "title": "Healthy Diet",
        "description": "Please eat a healthy breakfast, lunch and dinner",
        "status": "active",
        "version": "1.0.0",
        "category_code": "diet",
        "kind": "task",
        "completion_method": "manual",
        "data_trigger_types": None,
        "confirmation_prompt": "Did you eat a healthy diet today?",
        "content": {},
        "default_timing": {
            "period": 1,
            "frequency": 3,
            "timeOfDay": [],
            "periodUnit": "d",
            "windowMinutes": 720,
        },
    },
]

# Instruction template - a care plan template that references activity templates
INSTRUCTION_TEMPLATES = [
    {
        "id": UUID("a3224eb8-9f6d-45cd-8f34-51358ee071b9"),
        "name": "hypertension-management-plan",
        "title": "Hypertension Management Plan",
        "description": "A comprehensive plan to manage hypertension through medication, monitoring, exercise, and diet.",
        "status": "active",
        "version": "1.0.0",
        "content": {
            "sections": [
                {
                    "id": "8f70922e-080f-4643-af39-ecc1132c2892",
                    "title": "Medication",
                    "items": [
                        {
                            "id": "c0a0fd1c-3b40-47fe-8d91-c1fa49f823cd",
                            "activity_template_id": "42519e56-3f2e-4228-8d4d-3937f82e8c90",
                        }
                    ],
                },
                {
                    "id": "c1f0c0e2-c67b-48a9-b6d1-8c563d7b59f6",
                    "title": "Daily Monitoring",
                    "items": [
                        {
                            "id": "bf48bd66-b081-4180-acad-cff09a25e7f8",
                            "activity_template_id": "7769a5bb-0967-443a-9411-c4d47e53c978",
                        }
                    ],
                },
                {
                    "id": "36062169-77c4-4022-9ba1-48d2d5d45419",
                    "title": "Exercise",
                    "items": [
                        {
                            "id": "8670cd86-43e7-42ed-ad96-0e5634d0eb6f",
                            "activity_template_id": "3b4b472e-388b-4cc9-9c14-19155adc21b6",
                        }
                    ],
                },
                {
                    "id": "a1c74bfa-d70d-41ce-8d94-9c98b6530450",
                    "title": "Diet",
                    "items": [
                        {
                            "id": "77588592-df01-4aab-a580-c1ae1d0e36cf",
                            "type": "activity_ref",
                            "activity_template_id": "9517cd87-5151-478c-aed8-84c6d525283a",
                        }
                    ],
                },
            ]
        },
        "notification_config": None,
    },
]


def seed_activity_templates(db) -> int:
    """Seed activity templates. Returns count of templates created."""
    created = 0
    for data in ACTIVITY_TEMPLATES:
        template_id = data["id"]
        stmt = select(ActivityTemplate).where(ActivityTemplate.id == template_id)
        existing = db.execute(stmt).scalar_one_or_none()

        if existing:
            print(f"  Activity template '{data['name']}' already exists, skipping")
            continue

        template = ActivityTemplate(
            id=template_id,
            organization_id=None,  # System-wide template
            name=data["name"],
            title=data["title"],
            description=data["description"],
            status=data["status"],
            version=data["version"],
            category_code=data["category_code"],
            kind=data["kind"],
            completion_method=data["completion_method"],
            data_trigger_types=data["data_trigger_types"],
            confirmation_prompt=data["confirmation_prompt"],
            content=data["content"],
            default_timing=data["default_timing"],
        )
        db.add(template)
        print(f"  Created activity template: {data['title']}")
        created += 1

    return created


def seed_instruction_templates(db) -> int:
    """Seed instruction templates. Returns count of templates created."""
    created = 0
    for data in INSTRUCTION_TEMPLATES:
        template_id = data["id"]
        stmt = select(InstructionTemplate).where(InstructionTemplate.id == template_id)
        existing = db.execute(stmt).scalar_one_or_none()

        if existing:
            print(f"  Instruction template '{data['name']}' already exists, skipping")
            continue

        template = InstructionTemplate(
            id=template_id,
            organization_id=None,  # System-wide template
            name=data["name"],
            title=data["title"],
            description=data["description"],
            status=data["status"],
            version=data["version"],
            content=data["content"],
            notification_config=data["notification_config"],
        )
        db.add(template)
        print(f"  Created instruction template: {data['title']}")
        created += 1

    return created


def seed_all() -> None:
    """Seed all instruction and activity templates."""
    db = SessionLocal()

    try:
        print("Seeding activity templates...")
        activity_count = seed_activity_templates(db)

        print("Seeding instruction templates...")
        instruction_count = seed_instruction_templates(db)

        db.commit()

        print()
        print(f"Seeding complete!")
        print(f"  Activity templates: {activity_count} created")
        print(f"  Instruction templates: {instruction_count} created")

    except Exception as e:
        db.rollback()
        print(f"Error seeding templates: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_all()
