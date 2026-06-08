"""Clinical action model - tracks clinician actions on patients."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_50, str_255


class ClinicalAction(BaseDbModel):
    """Clinical action logged by a practitioner for a patient."""

    __tablename__ = "sl_clinical_action"

    id: Mapped[PrimaryKey[UUID]]

    # Patient
    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_patient.id", ondelete="CASCADE"),
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_organization.id", ondelete="CASCADE"),
        index=True,
    )

    # Practitioner who performed the action
    practitioner_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_practitioner.id", ondelete="SET NULL"),
        index=True,
    )

    # Action details
    action_type: Mapped[str_50]  # phone, in-person, order, education, escalation, note
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional: link to related alerts
    related_alert_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Timing
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        index=True,
    )

    # Relationships
    patient: Mapped["Patient"] = relationship(back_populates="clinical_actions")
    organization: Mapped["Organization"] = relationship(foreign_keys=[organization_id])
    practitioner: Mapped["Practitioner"] = relationship(foreign_keys=[practitioner_id])

    @property
    def practitioner_name(self) -> str:
        """Get practitioner display name."""
        if self.practitioner:
            return f"{self.practitioner.first_name} {self.practitioner.last_name}"
        return "Unknown"

    @property
    def category_display(self) -> str:
        """Get human-readable category name."""
        display_map = {
            "phone": "Phone Call",
            "in-person": "In-Person Visit",
            "order": "Order Placed",
            "education": "Education Provided",
            "escalation": "Escalation",
            "note": "Clinical Note",
        }
        return display_map.get(self.action_type, self.action_type.title())
