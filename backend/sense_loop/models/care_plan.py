"""Care plan model - patient discharge instructions."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_50, str_100, str_255


class CarePlan(BaseDbModel):
    """Patient care plan with discharge instructions."""

    __tablename__ = "sl_care_plan"

    id: Mapped[PrimaryKey[UUID]]

    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_patient.id", ondelete="CASCADE"),
        index=True,
    )

    # Care plan info
    title: Mapped[str_255]
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Type and status
    plan_type: Mapped[str_50]  # discharge, follow_up, medication, activity, dietary
    status: Mapped[str_50] = mapped_column(default="active", index=True)
    # Statuses: draft, active, completed, cancelled

    # Validity
    start_date: Mapped[date]
    end_date: Mapped[date | None] = mapped_column(nullable=True)

    # Content
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Structured content for different plan types
    content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Example for discharge plan:
    # {
    #     "medications": [
    #         {"name": "...", "dosage": "...", "frequency": "...", "notes": "..."}
    #     ],
    #     "activity_restrictions": ["...", "..."],
    #     "warning_signs": ["...", "..."],
    #     "follow_up_appointments": [
    #         {"type": "...", "date": "...", "provider": "..."}
    #     ],
    #     "emergency_contacts": [
    #         {"name": "...", "phone": "...", "relation": "..."}
    #     ]
    # }

    # Goals
    goals: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # [
    #     {"id": "...", "description": "Walk 30 minutes daily", "target": 30, "unit": "minutes"}
    # ]

    # Linked questionnaire
    questionnaire_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_questionnaire.id", ondelete="SET NULL"),
        nullable=True,
    )
    questionnaire_schedule: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # {"frequency": "daily", "time": "09:00", "days": [1, 2, 3, 4, 5, 6, 7]}

    # Attribution
    created_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_practitioner.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_practitioner.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Timestamps
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    patient: Mapped["Patient"] = relationship(back_populates="care_plans")
    questionnaire: Mapped["Questionnaire | None"] = relationship(
        foreign_keys=[questionnaire_id],
    )
    created_by: Mapped["Practitioner | None"] = relationship(
        foreign_keys=[created_by_id],
    )
    updated_by: Mapped["Practitioner | None"] = relationship(
        foreign_keys=[updated_by_id],
    )

    @property
    def is_active(self) -> bool:
        """Check if care plan is currently active."""
        if self.status != "active":
            return False
        today = date.today()
        if today < self.start_date:
            return False
        if self.end_date and today > self.end_date:
            return False
        return True
