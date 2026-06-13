"""Instruction Template model - complete instruction/care plan templates."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_50, str_100, str_255

if TYPE_CHECKING:
    from .activity_template import ActivityTemplate
    from .organization import Organization
    from .practitioner import Practitioner


class InstructionTemplate(BaseDbModel):
    """Complete instruction template combining activities into sections.

    Examples: "Post-Angioplasty Discharge Instructions", "Hypertension Management Plan"

    Templates are associated with health focuses (surgery types, chronic conditions)
    and can be assigned to patients via PatientInstructionPlan.
    """

    __tablename__ = "sl_instruction_template"

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

    # Content structure (JSONB)
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Example content:
    # {
    #     "sections": [
    #         {
    #             "id": "wound-care",
    #             "title": "Wound Care",
    #             "description": "How to care for your surgical incision",
    #             "priority": "routine",
    #             "items": [
    #                 {
    #                     "id": "daily-wound-check",
    #                     "type": "activity_ref",
    #                     "activity_template_id": "uuid",
    #                     "timing": {...}  # Override default timing
    #                 },
    #                 {
    #                     "id": "keep-dry",
    #                     "type": "inline",
    #                     "title": "Keep incision dry for 48 hours",
    #                     "description": "Do not submerge in water..."
    #                 }
    #             ]
    #         },
    #         {
    #             "id": "warning-signs",
    #             "title": "When to Call Your Doctor",
    #             "priority": "urgent",
    #             "items": [...]
    #         }
    #     ]
    # }

    # Notification defaults for this template
    notification_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Example:
    # {
    #     "reminder_minutes_before": 15,
    #     "overdue_minutes_after": 30,
    #     "daily_summary_enabled": true
    # }

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
    health_focuses: Mapped[list["InstructionTemplateHealthFocus"]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
    )

    @property
    def is_shared(self) -> bool:
        """Check if this is a shared (global) template."""
        return self.organization_id is None

    @property
    def health_focus_codes(self) -> list[str]:
        """Get list of health focus codes."""
        return [hf.health_focus_code for hf in self.health_focuses]

    @property
    def section_count(self) -> int:
        """Get number of sections in the template."""
        sections = self.content.get("sections", [])
        return len(sections)

    def get_activity_template_ids(self) -> list[str]:
        """Get all activity template IDs referenced in this template."""
        ids = []
        for section in self.content.get("sections", []):
            for item in section.get("items", []):
                if item.get("activity_template_id"):
                    ids.append(item["activity_template_id"])
        return ids


class InstructionTemplateHealthFocus(BaseDbModel):
    """Association between InstructionTemplate and health focus codes.

    Health focus codes can represent:
    - Surgery types (post-angioplasty, post-bypass, etc.)
    - Chronic conditions (hypertension, diabetes, etc.)
    - Preventive programs (cardiac-rehab, weight-management, etc.)
    """

    __tablename__ = "sl_instruction_template_health_focus"
    __table_args__ = (
        UniqueConstraint("template_id", "health_focus_code", name="uq_template_health_focus"),
    )

    id: Mapped[PrimaryKey[UUID]]

    template_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_instruction_template.id", ondelete="CASCADE"),
        index=True,
    )

    # Health focus code (references ValueSet item)
    health_focus_code: Mapped[str_100]

    # Relationships
    template: Mapped["InstructionTemplate"] = relationship(
        back_populates="health_focuses",
    )
