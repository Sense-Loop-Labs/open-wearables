"""Questionnaire models - assessment templates."""

from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_50, str_100, str_255


class Questionnaire(BaseDbModel):
    """Assessment questionnaire template."""

    __tablename__ = "sl_questionnaire"

    id: Mapped[PrimaryKey[UUID]]

    # Ownership
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_organization.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )  # None = system-wide questionnaire

    # Questionnaire info
    title: Mapped[str_255]
    code: Mapped[str_100]  # e.g., 'daily_check_in', 'pain_assessment'
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Type
    questionnaire_type: Mapped[str_50]  # daily, weekly, on_demand, triggered
    category: Mapped[str_50]  # symptom, pain, mood, activity, medication

    # Settings
    estimated_minutes: Mapped[int | None] = mapped_column(nullable=True)
    allow_skip: Mapped[bool] = mapped_column(default=False)
    require_completion: Mapped[bool] = mapped_column(default=True)

    # Scoring (if applicable)
    has_scoring: Mapped[bool] = mapped_column(default=False)
    scoring_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # {
    #     "method": "sum",  # sum, average, weighted
    #     "ranges": [
    #         {"min": 0, "max": 3, "label": "Low", "severity": "info"},
    #         {"min": 4, "max": 7, "label": "Moderate", "severity": "warning"},
    #         {"min": 8, "max": 10, "label": "High", "severity": "critical"}
    #     ]
    # }

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(default=1)

    # Relationships
    organization: Mapped["Organization | None"] = relationship(
        foreign_keys=[organization_id],
    )
    questions: Mapped[list["QuestionnaireQuestion"]] = relationship(
        back_populates="questionnaire",
        cascade="all, delete-orphan",
        order_by="QuestionnaireQuestion.order",
    )
    responses: Mapped[list["QuestionnaireResponse"]] = relationship(
        back_populates="questionnaire",
    )
    assignments: Mapped[list["PatientQuestionnaireAssignment"]] = relationship(
        back_populates="questionnaire",
    )


class QuestionnaireQuestion(BaseDbModel):
    """Individual question in a questionnaire."""

    __tablename__ = "sl_questionnaire_question"

    id: Mapped[PrimaryKey[UUID]]

    questionnaire_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_questionnaire.id", ondelete="CASCADE"),
        index=True,
    )

    # Question info
    code: Mapped[str_100]  # e.g., 'pain_level', 'mobility'
    text: Mapped[str] = mapped_column(Text)
    help_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Question type
    question_type: Mapped[str_50]
    # Types: text, number, scale, single_choice, multi_choice, boolean, date, time

    # Order
    order: Mapped[int] = mapped_column(default=0)

    # Validation
    is_required: Mapped[bool] = mapped_column(default=True)
    validation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # {
    #     "min": 0,
    #     "max": 10,
    #     "min_length": 10,
    #     "max_length": 500,
    #     "pattern": "..."
    # }

    # Options (for choice questions)
    options: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # [
    #     {"value": "1", "label": "No pain", "score": 0},
    #     {"value": "2", "label": "Mild pain", "score": 1},
    #     ...
    # ]

    # Conditional display
    condition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # {"question_code": "has_pain", "operator": "equals", "value": true}

    # Scoring
    score_weight: Mapped[float | None] = mapped_column(nullable=True)

    # Alert trigger
    alert_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # {
    #     "trigger_values": ["severe", "critical"],
    #     "alert_severity": "warning",
    #     "alert_message": "Patient reported severe pain"
    # }

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    questionnaire: Mapped["Questionnaire"] = relationship(back_populates="questions")
