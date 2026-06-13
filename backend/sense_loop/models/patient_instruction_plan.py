"""Patient Instruction Plan model - links patients to instruction templates."""

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_50

if TYPE_CHECKING:
    from .instruction_template import InstructionTemplate
    from .patient import Patient
    from .patient_instruction_task import PatientInstructionTask
    from .practitioner import Practitioner


class PatientInstructionPlan(BaseDbModel):
    """Patient-specific instance of an instruction template.

    Links a patient to a template with optional customizations.
    Tasks are generated from this plan based on timing configurations.
    """

    __tablename__ = "sl_patient_instruction_plan"

    id: Mapped[PrimaryKey[UUID]]

    # Patient and template
    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_patient.id", ondelete="CASCADE"),
        index=True,
    )
    template_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_instruction_template.id", ondelete="RESTRICT"),
        index=True,
    )

    # Status
    status: Mapped[str_50] = mapped_column(default="active")  # draft, active, completed, cancelled

    # Effective period
    effective_start: Mapped[datetime]
    effective_end: Mapped[datetime | None] = mapped_column(nullable=True)

    # Customizations (overrides template content for this patient)
    customizations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Example customizations:
    # {
    #     "sections": {
    #         "wound-care": {
    #             "items": {
    #                 "daily-wound-check": {
    #                     "timing": {
    #                         "boundsDurationDays": 21  # Extended from 14
    #                     }
    #                 }
    #             }
    #         }
    #     },
    #     "added_items": [
    #         {
    #             "section_id": "medications",
    #             "item": {
    #                 "id": "custom-antibiotic",
    #                 "type": "inline",
    #                 "title": "Take Amoxicillin 500mg",
    #                 "timing": {...}
    #             }
    #         }
    #     ],
    #     "removed_items": ["some-item-id"]
    # }

    # Resolved content (cached, denormalized for fast reads)
    # This is the merged result of template + customizations
    resolved_content: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Task generation tracking
    tasks_generated_through: Mapped[date | None] = mapped_column(nullable=True)

    # Reference date for relative timing (surgery_date, assignment_date, etc.)
    reference_date: Mapped[date | None] = mapped_column(nullable=True)
    reference_type: Mapped[str_50 | None] = mapped_column(
        nullable=True
    )  # surgery_date, assignment_date, discharge_date

    # Audit
    assigned_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_practitioner.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        onupdate=datetime.utcnow,
    )
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    patient: Mapped["Patient"] = relationship(
        back_populates="instruction_plans",
    )
    template: Mapped["InstructionTemplate"] = relationship(
        foreign_keys=[template_id],
    )
    assigned_by: Mapped["Practitioner | None"] = relationship(
        foreign_keys=[assigned_by_id],
    )
    tasks: Mapped[list["PatientInstructionTask"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="PatientInstructionTask.scheduled_at",
    )

    @property
    def is_active(self) -> bool:
        """Check if plan is currently active."""
        if self.status != "active":
            return False
        now = datetime.utcnow()
        if now < self.effective_start:
            return False
        if self.effective_end and now > self.effective_end:
            return False
        return True

    @property
    def days_active(self) -> int | None:
        """Calculate days since plan became active."""
        if not self.effective_start:
            return None
        return (datetime.utcnow() - self.effective_start).days
