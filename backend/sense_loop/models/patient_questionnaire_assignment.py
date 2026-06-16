"""Patient Questionnaire Assignment model - tracks recurring questionnaire assignments."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_50

if TYPE_CHECKING:
    from .patient import Patient
    from .practitioner import Practitioner
    from .questionnaire import Questionnaire


class PatientQuestionnaireAssignment(BaseDbModel):
    """Tracks recurring questionnaire assignments to patients.

    For daily/weekly questionnaires, this model tracks the assignment
    and is used by the scheduler to create new QuestionnaireResponse
    records automatically.
    """

    __tablename__ = "sl_patient_questionnaire_assignment"

    id: Mapped[PrimaryKey[UUID]]

    # Patient and questionnaire
    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_patient.id", ondelete="CASCADE"),
        index=True,
    )
    questionnaire_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_questionnaire.id", ondelete="CASCADE"),
        index=True,
    )

    # Status: active, paused, cancelled
    status: Mapped[str_50] = mapped_column(default="active")

    # Effective period (when the assignment is active)
    effective_start: Mapped[datetime]
    effective_end: Mapped[datetime | None] = mapped_column(nullable=True)

    # Track when we last generated a response for this assignment
    last_generated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Who assigned it
    assigned_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_practitioner.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        default=None, onupdate=datetime.utcnow
    )

    # Relationships
    patient: Mapped["Patient"] = relationship(
        back_populates="questionnaire_assignments",
        foreign_keys=[patient_id],
    )
    questionnaire: Mapped["Questionnaire"] = relationship(
        back_populates="assignments",
        foreign_keys=[questionnaire_id],
    )
    assigned_by: Mapped["Practitioner | None"] = relationship(
        foreign_keys=[assigned_by_id],
    )

    def __repr__(self) -> str:
        return (
            f"<PatientQuestionnaireAssignment {self.id} "
            f"patient={self.patient_id} questionnaire={self.questionnaire_id}>"
        )

    @property
    def is_active(self) -> bool:
        """Check if assignment is currently active."""
        if self.status != "active":
            return False
        now = datetime.utcnow()
        if self.effective_start > now:
            return False
        if self.effective_end and self.effective_end < now:
            return False
        return True
