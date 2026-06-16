#!/usr/bin/env python3
"""Seed test questionnaires for development."""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from uuid import uuid4

from sqlalchemy import select

from app.database import SessionLocal
from sense_loop.models import Questionnaire, QuestionnaireQuestion

# Daily Symptom Check questionnaire definition
DAILY_SYMPTOM_CHECK = {
    "title": "Daily Symptom Check",
    "code": "daily_symptom_check",
    "description": "A brief daily check-in to monitor your recovery progress and symptoms.",
    "questionnaire_type": "daily",
    "category": "symptom",
    "estimated_minutes": 3,
    "allow_skip": False,
    "require_completion": True,
    "has_scoring": True,
    "scoring_config": {
        "method": "sum",
        "ranges": [
            {"min": 0, "max": 3, "label": "Low", "severity": "info"},
            {"min": 4, "max": 7, "label": "Moderate", "severity": "warning"},
            {"min": 8, "max": 10, "label": "High", "severity": "critical"},
        ],
    },
    "questions": [
        {
            "code": "pain_level",
            "text": "How would you rate your pain level right now?",
            "help_text": "0 means no pain, 10 means the worst pain imaginable",
            "question_type": "scale",
            "order": 1,
            "is_required": True,
            "validation": {"min": 0, "max": 10},
            "options": None,
            "condition": None,
            "score_weight": 1.0,
            "alert_config": {
                "trigger_values": [8, 9, 10],
                "alert_severity": "warning",
                "alert_message": "Patient reported severe pain (level {value})",
            },
        },
        {
            "code": "pain_location",
            "text": "Where is your pain located?",
            "help_text": "Select all areas where you're experiencing pain",
            "question_type": "multi_choice",
            "order": 2,
            "is_required": False,
            "validation": None,
            "options": [
                {"value": "incision_site", "label": "Incision site", "score": 0},
                {"value": "head", "label": "Head", "score": 0},
                {"value": "chest", "label": "Chest", "score": 0},
                {"value": "abdomen", "label": "Abdomen", "score": 0},
                {"value": "back", "label": "Back", "score": 0},
                {"value": "joints", "label": "Joints", "score": 0},
                {"value": "other", "label": "Other", "score": 0},
            ],
            "condition": {"question_code": "pain_level", "operator": "greater_than", "value": 0},
            "score_weight": None,
            "alert_config": None,
        },
        {
            "code": "took_medication",
            "text": "Have you taken your prescribed pain medication today?",
            "help_text": None,
            "question_type": "boolean",
            "order": 3,
            "is_required": True,
            "validation": None,
            "options": None,
            "condition": None,
            "score_weight": None,
            "alert_config": None,
        },
        {
            "code": "medication_effectiveness",
            "text": "How effective was your pain medication?",
            "help_text": "Rate how well your medication is controlling your pain",
            "question_type": "single_choice",
            "order": 4,
            "is_required": True,
            "validation": None,
            "options": [
                {"value": "very_effective", "label": "Very effective - pain well controlled", "score": 0},
                {"value": "somewhat_effective", "label": "Somewhat effective - pain reduced", "score": 1},
                {"value": "slightly_effective", "label": "Slightly effective - minimal relief", "score": 2},
                {"value": "not_effective", "label": "Not effective - no relief", "score": 3},
            ],
            "condition": {"question_code": "took_medication", "operator": "equals", "value": True},
            "score_weight": 1.0,
            "alert_config": {
                "trigger_values": ["not_effective"],
                "alert_severity": "warning",
                "alert_message": "Patient reports pain medication is not effective",
            },
        },
        {
            "code": "concerning_symptoms",
            "text": "Are you experiencing any of these concerning symptoms?",
            "help_text": "Select all that apply",
            "question_type": "multi_choice",
            "order": 5,
            "is_required": True,
            "validation": None,
            "options": [
                {"value": "fever", "label": "Fever or chills", "score": 2},
                {"value": "bleeding", "label": "Excessive bleeding", "score": 3},
                {"value": "redness", "label": "Increased redness around incision", "score": 2},
                {"value": "drainage", "label": "Unusual drainage from wound", "score": 2},
                {"value": "breathing", "label": "Difficulty breathing", "score": 3},
                {"value": "nausea", "label": "Severe nausea or vomiting", "score": 1},
                {"value": "none", "label": "None of the above", "score": 0},
            ],
            "condition": None,
            "score_weight": 1.0,
            "alert_config": {
                "trigger_values": ["fever", "bleeding", "redness", "drainage", "breathing"],
                "alert_severity": "critical",
                "alert_message": "Patient reported concerning symptom: {value}",
            },
        },
        {
            "code": "mobility_level",
            "text": "How is your mobility today?",
            "help_text": None,
            "question_type": "single_choice",
            "order": 6,
            "is_required": True,
            "validation": None,
            "options": [
                {"value": "normal", "label": "Normal - moving around easily", "score": 0},
                {"value": "limited", "label": "Limited - moving slowly but managing", "score": 1},
                {"value": "difficult", "label": "Difficult - need assistance", "score": 2},
                {"value": "unable", "label": "Unable - cannot move without help", "score": 3},
            ],
            "condition": None,
            "score_weight": 1.0,
            "alert_config": {
                "trigger_values": ["unable"],
                "alert_severity": "warning",
                "alert_message": "Patient reports inability to move without assistance",
            },
        },
        {
            "code": "additional_notes",
            "text": "Any additional notes or concerns?",
            "help_text": "Optional - describe anything else your care team should know",
            "question_type": "text",
            "order": 7,
            "is_required": False,
            "validation": {"max_length": 1000},
            "options": None,
            "condition": None,
            "score_weight": None,
            "alert_config": None,
        },
    ],
}


def seed_questionnaires() -> None:
    """Seed test questionnaires if they don't exist."""
    db = SessionLocal()

    try:
        # Check if questionnaire exists
        stmt = select(Questionnaire).where(
            Questionnaire.code == DAILY_SYMPTOM_CHECK["code"],
            Questionnaire.organization_id.is_(None),
        )
        existing = db.execute(stmt).scalar_one_or_none()

        if existing:
            print(f"Questionnaire '{DAILY_SYMPTOM_CHECK['code']}' already exists, skipping")
            return

        # Create questionnaire
        questions_data = DAILY_SYMPTOM_CHECK.pop("questions")
        questionnaire = Questionnaire(
            id=uuid4(),
            organization_id=None,  # System-wide questionnaire
            **DAILY_SYMPTOM_CHECK,
        )
        db.add(questionnaire)

        # Create questions
        for q_data in questions_data:
            question = QuestionnaireQuestion(
                id=uuid4(),
                questionnaire_id=questionnaire.id,
                **q_data,
            )
            db.add(question)
            print(f"  Added question: {q_data['code']}")

        db.commit()
        print(f"\nCreated questionnaire: {DAILY_SYMPTOM_CHECK['title']}")
        print(f"  ID: {questionnaire.id}")
        print(f"  Code: {questionnaire.code}")
        print(f"  Questions: {len(questions_data)}")

    except Exception as e:
        db.rollback()
        print(f"Error seeding questionnaires: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_questionnaires()
