"""Activity Template model - reusable instruction building blocks."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_50, str_100, str_255

if TYPE_CHECKING:
    from .organization import Organization
    from .practitioner import Practitioner


class ActivityTemplate(BaseDbModel):
    """Reusable instruction building block.

    Examples: "Daily Wound Care", "BP Monitoring", "Medication Reminder"

    These can be referenced by InstructionTemplates to build complete
    discharge instructions or care plans.
    """

    __tablename__ = "sl_activity_template"

    id: Mapped[PrimaryKey[UUID]]

    # Organization (None = shared/global template)
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_organization.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Metadata
    name: Mapped[str_100] = mapped_column(unique=True)  # Machine-readable slug
    title: Mapped[str_255]  # Display name
    description: Mapped[str] = mapped_column(Text)  # Rich HTML content
    status: Mapped[str_50] = mapped_column(default="draft")  # draft, active, retired
    version: Mapped[str_50] = mapped_column(default="1.0.0")

    # Classification
    category_code: Mapped[str_50]  # wound-care, medications, activity, diet, etc.
    kind: Mapped[str_50] = mapped_column(default="task")  # task, service_request, medication_request

    # Task completion settings
    completion_method: Mapped[str_50] = mapped_column(default="manual")  # auto, manual, hybrid
    data_trigger_types: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)), nullable=True
    )  # For auto: ["blood_pressure", "heart_rate"]
    data_threshold: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # For auto with threshold: {"min_steps": 500}
    confirmation_prompt: Mapped[str_255 | None] = mapped_column(
        nullable=True
    )  # For manual: "Did you take your {medication_name}?"

    # Content (flexible JSONB structure)
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Example content:
    # {
    #     "instructions": "Keep the incision site clean and dry...",
    #     "warnings": ["Redness spreading", "Fever above 101°F"],
    #     "tips": ["Use a clean towel each time"],
    #     "resources": [{"type": "video", "title": "...", "url": "..."}]
    # }

    # Default timing (FHIR-compatible structure)
    default_timing: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Example timing:
    # {
    #     "frequency": 2,
    #     "period": 1,
    #     "periodUnit": "d",
    #     "timeOfDay": ["08:00", "20:00"],
    #     "boundsType": "duration",
    #     "boundsDurationDays": 14
    # }

    # FHIR interop
    code_system: Mapped[str_255 | None] = mapped_column(nullable=True)  # e.g., "http://snomed.info/sct"
    code_value: Mapped[str_50 | None] = mapped_column(nullable=True)  # e.g., "225358003"

    # Audit
    created_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_practitioner.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        onupdate=datetime.utcnow,
    )

    # Relationships
    organization: Mapped["Organization | None"] = relationship(
        foreign_keys=[organization_id],
    )
    created_by: Mapped["Practitioner | None"] = relationship(
        foreign_keys=[created_by_id],
    )

    @property
    def is_shared(self) -> bool:
        """Check if this is a shared (global) template."""
        return self.organization_id is None

    @property
    def is_auto_complete(self) -> bool:
        """Check if this activity can be auto-completed from data."""
        return self.completion_method in ("auto", "hybrid")
