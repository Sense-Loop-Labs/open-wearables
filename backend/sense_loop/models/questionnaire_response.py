"""Questionnaire response models - patient answers."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_50


class QuestionnaireResponse(BaseDbModel):
    """Patient's response to a questionnaire."""

    __tablename__ = "sl_questionnaire_response"

    id: Mapped[PrimaryKey[UUID]]

    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_patient.id", ondelete="CASCADE"),
        index=True,
    )
    questionnaire_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_questionnaire.id", ondelete="CASCADE"),
        index=True,
    )

    # Status
    status: Mapped[str_50] = mapped_column(default="in_progress", index=True)
    # Statuses: in_progress, completed, skipped, expired

    # Timing
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # If questionnaire was scheduled
    scheduled_for: Mapped[datetime | None] = mapped_column(nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Scoring (if applicable)
    total_score: Mapped[float | None] = mapped_column(nullable=True)
    score_interpretation: Mapped[str_50 | None] = mapped_column(nullable=True)
    # e.g., 'low', 'moderate', 'high'

    # Review
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    reviewed_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_practitioner.id", ondelete="SET NULL"),
        nullable=True,
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    patient: Mapped["Patient"] = relationship(back_populates="questionnaire_responses")
    questionnaire: Mapped["Questionnaire"] = relationship(back_populates="responses")
    reviewed_by: Mapped["Practitioner | None"] = relationship(
        foreign_keys=[reviewed_by_id],
    )
    answers: Mapped[list["QuestionnaireAnswer"]] = relationship(
        back_populates="response",
        cascade="all, delete-orphan",
    )

    @property
    def is_complete(self) -> bool:
        """Check if response is complete."""
        return self.status == "completed"

    @property
    def is_overdue(self) -> bool:
        """Check if response is overdue."""
        if not self.due_at or self.is_complete:
            return False
        return datetime.utcnow() > self.due_at


class QuestionnaireAnswer(BaseDbModel):
    """Individual answer to a questionnaire question."""

    __tablename__ = "sl_questionnaire_answer"

    id: Mapped[PrimaryKey[UUID]]

    response_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_questionnaire_response.id", ondelete="CASCADE"),
        index=True,
    )
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_questionnaire_question.id", ondelete="CASCADE"),
        index=True,
    )

    # Answer value (type depends on question type)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_number: Mapped[float | None] = mapped_column(nullable=True)
    value_boolean: Mapped[bool | None] = mapped_column(nullable=True)
    value_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # For multi-choice, date, time, etc.

    # Computed score for this answer
    score: Mapped[float | None] = mapped_column(nullable=True)

    # Was this answer skipped?
    skipped: Mapped[bool] = mapped_column(default=False)

    # Timing
    answered_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    response: Mapped["QuestionnaireResponse"] = relationship(back_populates="answers")
    question: Mapped["QuestionnaireQuestion"] = relationship()
