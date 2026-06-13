"""Patient instruction plan service - manage patient-specific instruction assignments."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from sense_loop.models import (
    InstructionTemplate,
    Patient,
    PatientInstructionPlan,
    Practitioner,
)

if TYPE_CHECKING:
    from sense_loop.services.task_generation_service import TaskGenerationService

logger = logging.getLogger(__name__)


class PatientInstructionPlanService:
    """Service for managing patient instruction plans."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(
        self, plan_id: UUID, *, load_template: bool = True
    ) -> PatientInstructionPlan | None:
        """Get plan by ID."""
        stmt = select(PatientInstructionPlan).where(PatientInstructionPlan.id == plan_id)

        if load_template:
            stmt = stmt.options(
                joinedload(PatientInstructionPlan.template),
                joinedload(PatientInstructionPlan.patient),
            )

        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_active_plans(self, patient_id: UUID) -> list[PatientInstructionPlan]:
        """Get all active plans for a patient."""
        stmt = (
            select(PatientInstructionPlan)
            .where(
                PatientInstructionPlan.patient_id == patient_id,
                PatientInstructionPlan.status == "active",
            )
            .options(joinedload(PatientInstructionPlan.template))
            .order_by(PatientInstructionPlan.created_at.desc())
        )

        return list(self.db.execute(stmt).unique().scalars().all())

    def list_for_patient(
        self,
        patient_id: UUID,
        *,
        status: str | None = None,
    ) -> list[PatientInstructionPlan]:
        """List all plans for a patient."""
        stmt = (
            select(PatientInstructionPlan)
            .where(PatientInstructionPlan.patient_id == patient_id)
            .options(joinedload(PatientInstructionPlan.template))
        )

        if status:
            stmt = stmt.where(PatientInstructionPlan.status == status)

        stmt = stmt.order_by(PatientInstructionPlan.created_at.desc())

        return list(self.db.execute(stmt).unique().scalars().all())

    def assign(
        self,
        *,
        patient: Patient,
        template: InstructionTemplate,
        assigned_by: Practitioner,
        effective_start: datetime | None = None,
        effective_end: datetime | None = None,
        customizations: dict | None = None,
        reference_date: date | None = None,
        reference_type: str | None = None,
        generate_tasks: bool = True,
        task_generation_service: "TaskGenerationService | None" = None,
    ) -> PatientInstructionPlan:
        """Assign an instruction template to a patient.

        Args:
            patient: Patient to assign to
            template: Template to assign
            assigned_by: Practitioner making the assignment
            effective_start: When the plan starts (default: now)
            effective_end: When the plan ends (default: None/ongoing)
            customizations: Patient-specific overrides
            reference_date: Reference date for relative timing (e.g., surgery_date)
            reference_type: Type of reference date (surgery_date, discharge_date, etc.)
            generate_tasks: Whether to generate tasks immediately
            task_generation_service: Service for task generation
        """
        if effective_start is None:
            effective_start = datetime.utcnow()

        # Determine reference date if not provided
        if reference_date is None and reference_type:
            if reference_type == "surgery_date" and patient.surgery_date:
                reference_date = patient.surgery_date
            elif reference_type == "discharge_date" and patient.discharge_date:
                reference_date = patient.discharge_date
            elif reference_type == "assignment_date":
                reference_date = effective_start.date()

        # Default reference type if we have surgery date
        if reference_date is None and patient.surgery_date:
            reference_date = patient.surgery_date
            reference_type = "surgery_date"
        elif reference_date is None:
            reference_date = effective_start.date()
            reference_type = "assignment_date"

        # Resolve the content (merge template + customizations)
        resolved_content = self._resolve_content(template, customizations)

        plan = PatientInstructionPlan(
            id=uuid4(),
            patient_id=patient.id,
            template_id=template.id,
            status="active",
            effective_start=effective_start,
            effective_end=effective_end,
            customizations=customizations,
            resolved_content=resolved_content,
            reference_date=reference_date,
            reference_type=reference_type,
            assigned_by_id=assigned_by.id,
        )

        self.db.add(plan)
        self.db.flush()

        logger.info(
            "Assigned instruction plan %s (template %s) to patient %s by %s",
            plan.id,
            template.name,
            patient.id,
            assigned_by.email,
        )

        # Generate initial tasks if requested
        if generate_tasks and task_generation_service:
            task_count = task_generation_service.ensure_tasks_generated(plan)
            logger.info("Generated %d tasks for plan %s", task_count, plan.id)

        return plan

    def update(
        self,
        plan: PatientInstructionPlan,
        *,
        customizations: dict | None = None,
        effective_end: datetime | None = None,
        regenerate_tasks: bool = True,
        task_generation_service: "TaskGenerationService | None" = None,
    ) -> PatientInstructionPlan:
        """Update a patient instruction plan.

        If customizations are changed and regenerate_tasks is True,
        pending tasks will be cancelled and regenerated.
        """
        customizations_changed = False

        if customizations is not None:
            customizations_changed = customizations != plan.customizations
            plan.customizations = customizations

            # Re-resolve content
            plan.resolved_content = self._resolve_content(
                plan.template, customizations
            )

        if effective_end is not None:
            plan.effective_end = effective_end

        plan.updated_at = datetime.utcnow()
        self.db.flush()

        logger.info("Updated instruction plan %s", plan.id)

        # Regenerate tasks if customizations changed
        if customizations_changed and regenerate_tasks and task_generation_service:
            cancelled, created = task_generation_service.regenerate_on_plan_change(plan)
            logger.info(
                "Regenerated tasks for plan %s: cancelled %d, created %d",
                plan.id,
                cancelled,
                created,
            )

        return plan

    def complete(self, plan: PatientInstructionPlan) -> PatientInstructionPlan:
        """Mark a plan as completed."""
        plan.status = "completed"
        plan.completed_at = datetime.utcnow()
        plan.updated_at = datetime.utcnow()
        self.db.flush()

        logger.info("Completed instruction plan %s", plan.id)
        return plan

    def cancel(
        self,
        plan: PatientInstructionPlan,
        *,
        cancel_pending_tasks: bool = True,
    ) -> PatientInstructionPlan:
        """Cancel a plan."""
        plan.status = "cancelled"
        plan.cancelled_at = datetime.utcnow()
        plan.updated_at = datetime.utcnow()

        # Cancel pending tasks
        if cancel_pending_tasks:
            for task in plan.tasks:
                if task.status == "pending":
                    task.status = "cancelled"
                    task.updated_at = datetime.utcnow()

        self.db.flush()

        logger.info("Cancelled instruction plan %s", plan.id)
        return plan

    def _resolve_content(
        self,
        template: InstructionTemplate,
        customizations: dict | None,
    ) -> dict:
        """Resolve template content with patient customizations.

        Merges customizations into the template content:
        - Timing overrides
        - Added items
        - Removed items
        - Description overrides
        """
        from sense_loop.services.instruction_template_service import (
            InstructionTemplateService,
        )

        # First resolve activity references to get timing, titles, etc.
        template_service = InstructionTemplateService(self.db)
        content = template_service.get_resolved_content(template)

        if not customizations:
            return content

        sections = content.get("sections", [])

        # Apply section/item customizations
        section_customizations = customizations.get("sections", {})
        for section in sections:
            section_id = section.get("id")
            if section_id and section_id in section_customizations:
                section_custom = section_customizations[section_id]

                # Apply item customizations
                item_customizations = section_custom.get("items", {})
                for item in section.get("items", []):
                    item_id = item.get("id")
                    if item_id and item_id in item_customizations:
                        item_custom = item_customizations[item_id]

                        # Merge timing override
                        if "timing" in item_custom:
                            base_timing = item.get("timing", {})
                            item["timing"] = {**base_timing, **item_custom["timing"]}

                        # Merge other overrides
                        for key in ["title", "description", "priority"]:
                            if key in item_custom:
                                item[key] = item_custom[key]

        # Add custom items
        added_items = customizations.get("added_items", [])
        for added in added_items:
            section_id = added.get("section_id")
            item = added.get("item")
            if section_id and item:
                # Find section and add item
                for section in sections:
                    if section.get("id") == section_id:
                        section.setdefault("items", []).append(item)
                        break

        # Remove items
        removed_items = set(customizations.get("removed_items", []))
        if removed_items:
            for section in sections:
                section["items"] = [
                    item
                    for item in section.get("items", [])
                    if item.get("id") not in removed_items
                ]

        content["sections"] = sections
        return content

    def get_resolved_content_with_activities(
        self, plan: PatientInstructionPlan
    ) -> dict:
        """Get plan content with activity references fully resolved.

        This is used for mobile app delivery where we need the complete
        instruction details including activity descriptions.
        """
        from sense_loop.services.instruction_template_service import (
            InstructionTemplateService,
        )

        template_service = InstructionTemplateService(self.db)

        # Get resolved content from template
        resolved = template_service.get_resolved_content(plan.template)

        # Apply patient customizations
        return self._resolve_content(
            type("Template", (), {"content": resolved})(),  # Duck type
            plan.customizations,
        )
