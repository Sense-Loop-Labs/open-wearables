"""ValueSet models for flexible code lists."""

from uuid import UUID

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_50, str_100, str_255


class ValueSet(BaseDbModel):
    """A set of coded values (e.g., surgery types, vital sign types).

    Follows FHIR ValueSet pattern for flexibility and future compatibility.
    Can be system-wide (organization_id=None) or org-specific.
    """

    __tablename__ = "sl_value_set"
    __table_args__ = (
        UniqueConstraint("code", "organization_id", name="uq_value_set_code_org"),
    )

    id: Mapped[PrimaryKey[UUID]]

    # Unique identifier for this value set (e.g., "surgery-types", "vital-sign-types")
    code: Mapped[str_100] = mapped_column(index=True)

    # Human-readable name
    name: Mapped[str_255]

    # Description of what this value set contains
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Organization scope
    # null = system-wide (available to all orgs)
    # set = org-specific (overrides or extends system-wide)
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_organization.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    organization: Mapped["Organization | None"] = relationship(
        foreign_keys=[organization_id],
    )
    items: Mapped[list["ValueSetItem"]] = relationship(
        back_populates="value_set",
        cascade="all, delete-orphan",
        order_by="ValueSetItem.sort_order",
    )


class ValueSetItem(BaseDbModel):
    """An item within a value set.

    Represents a single coded concept with optional metadata.
    """

    __tablename__ = "sl_value_set_item"
    __table_args__ = (
        UniqueConstraint("value_set_id", "code", name="uq_value_set_item_code"),
    )

    id: Mapped[PrimaryKey[UUID]]

    # Parent value set
    value_set_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_value_set.id", ondelete="CASCADE"),
        index=True,
    )

    # Code for this item (e.g., "418285008" for Angioplasty)
    code: Mapped[str_100]

    # Display name (e.g., "Angioplasty")
    display: Mapped[str_255]

    # Coding system (e.g., "http://snomed.info/sct", "internal")
    coding_system: Mapped[str_255 | None] = mapped_column(nullable=True)

    # Sort order for display
    sort_order: Mapped[int] = mapped_column(default=0)

    # Additional data (e.g., default alert protocol, instructions)
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    value_set: Mapped["ValueSet"] = relationship(back_populates="items")
