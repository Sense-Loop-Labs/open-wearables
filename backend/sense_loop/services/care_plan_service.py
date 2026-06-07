"""Care plan service - patient care plan management."""

from __future__ import annotations

import logging
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from sense_loop.models import CarePlan, Patient

logger = logging.getLogger(__name__)


class CarePlanService:
    """Service for managing patient care plans."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, care_plan_id: UUID) -> CarePlan | None:
        """Get care plan by ID."""
        stmt = (
            select(CarePlan)
            .where(CarePlan.id == care_plan_id)
            .options(
                joinedload(CarePlan.patient),
                joinedload(CarePlan.questionnaire),
            )
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_active_for_patient(self, patient_id: UUID) -> list[CarePlan]:
        """Get all active care plans for a patient."""
        today = date.today()
        stmt = (
            select(CarePlan)
            .where(
                CarePlan.patient_id == patient_id,
                CarePlan.status == "active",
                CarePlan.start_date <= today,
            )
            .options(joinedload(CarePlan.questionnaire))
            .order_by(CarePlan.created_at.desc())
        )

        plans = self.db.execute(stmt).unique().scalars().all()

        # Filter by end date
        return [p for p in plans if p.end_date is None or p.end_date >= today]

    def list_for_patient(
        self,
        patient_id: UUID,
        *,
        status: str | None = None,
        plan_type: str | None = None,
    ) -> list[CarePlan]:
        """List all care plans for a patient."""
        stmt = (
            select(CarePlan)
            .where(CarePlan.patient_id == patient_id)
            .options(joinedload(CarePlan.questionnaire))
        )

        if status:
            stmt = stmt.where(CarePlan.status == status)

        if plan_type:
            stmt = stmt.where(CarePlan.plan_type == plan_type)

        stmt = stmt.order_by(CarePlan.created_at.desc())

        return list(self.db.execute(stmt).unique().scalars().all())

    def create(
        self,
        patient_id: UUID,
        title: str,
        plan_type: str,
        start_date: date,
        *,
        description: str | None = None,
        end_date: date | None = None,
        instructions: str | None = None,
        content: dict | None = None,
        goals: list | None = None,
        questionnaire_id: UUID | None = None,
        questionnaire_schedule: dict | None = None,
        created_by_id: UUID | None = None,
    ) -> CarePlan:
        """Create a new care plan."""
        care_plan = CarePlan(
            id=uuid4(),
            patient_id=patient_id,
            title=title,
            description=description,
            plan_type=plan_type,
            status="active",
            start_date=start_date,
            end_date=end_date,
            instructions=instructions,
            content=content,
            goals=goals,
            questionnaire_id=questionnaire_id,
            questionnaire_schedule=questionnaire_schedule,
            created_by_id=created_by_id,
        )

        self.db.add(care_plan)
        self.db.flush()

        logger.info("Created care plan %s for patient %s", care_plan.id, patient_id)
        return care_plan

    def update(
        self,
        care_plan: CarePlan,
        *,
        title: str | None = None,
        description: str | None = None,
        instructions: str | None = None,
        content: dict | None = None,
        goals: list | None = None,
        end_date: date | None = None,
        questionnaire_id: UUID | None = None,
        questionnaire_schedule: dict | None = None,
        updated_by_id: UUID | None = None,
    ) -> CarePlan:
        """Update a care plan."""
        if title is not None:
            care_plan.title = title
        if description is not None:
            care_plan.description = description
        if instructions is not None:
            care_plan.instructions = instructions
        if content is not None:
            care_plan.content = content
        if goals is not None:
            care_plan.goals = goals
        if end_date is not None:
            care_plan.end_date = end_date
        if questionnaire_id is not None:
            care_plan.questionnaire_id = questionnaire_id
        if questionnaire_schedule is not None:
            care_plan.questionnaire_schedule = questionnaire_schedule

        care_plan.updated_by_id = updated_by_id
        care_plan.updated_at = datetime.utcnow()

        self.db.flush()

        logger.info("Updated care plan %s", care_plan.id)
        return care_plan

    def complete(self, care_plan: CarePlan) -> CarePlan:
        """Mark a care plan as completed."""
        care_plan.status = "completed"
        care_plan.completed_at = datetime.utcnow()
        care_plan.updated_at = datetime.utcnow()

        self.db.flush()

        logger.info("Completed care plan %s", care_plan.id)
        return care_plan

    def cancel(self, care_plan: CarePlan) -> CarePlan:
        """Cancel a care plan."""
        care_plan.status = "cancelled"
        care_plan.updated_at = datetime.utcnow()

        self.db.flush()

        logger.info("Cancelled care plan %s", care_plan.id)
        return care_plan

    def get_discharge_plan(self, patient_id: UUID) -> CarePlan | None:
        """Get the patient's discharge care plan."""
        stmt = (
            select(CarePlan)
            .where(
                CarePlan.patient_id == patient_id,
                CarePlan.plan_type == "discharge",
                CarePlan.status == "active",
            )
            .options(joinedload(CarePlan.questionnaire))
            .order_by(CarePlan.created_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def parse_discharge_content(self, care_plan: CarePlan) -> dict:
        """Parse discharge care plan content into structured format."""
        content = care_plan.content or {}

        return {
            "medications": content.get("medications", []),
            "activity_restrictions": content.get("activity_restrictions", []),
            "warning_signs": content.get("warning_signs", []),
            "follow_up_appointments": content.get("follow_up_appointments", []),
            "emergency_contacts": content.get("emergency_contacts", []),
            "dietary_restrictions": content.get("dietary_restrictions", []),
            "wound_care": content.get("wound_care", []),
            "additional_instructions": content.get("additional_instructions", ""),
        }
