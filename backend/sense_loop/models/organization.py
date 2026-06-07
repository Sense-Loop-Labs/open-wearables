"""Organization model for multi-tenancy."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, Unique, str_100, str_255


class Organization(BaseDbModel):
    """Multi-tenant organization."""

    __tablename__ = "sl_organization"

    id: Mapped[PrimaryKey[UUID]]

    # Organization info
    name: Mapped[str_255]
    slug: Mapped[Unique[str_100]]  # URL-friendly identifier
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Contact info
    contact_email: Mapped[str_255 | None]
    contact_phone: Mapped[str_100 | None]
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Settings stored as JSONB for flexibility
    settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    # Example settings:
    # {
    #     "notification_preferences": {"email": true, "sms": true, "push": true},
    #     "alert_escalation_minutes": 30,
    #     "timezone": "America/New_York",
    #     "branding": {"logo_url": "...", "primary_color": "#..."}
    # }

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    practitioner_roles: Mapped[list["PractitionerRole"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    patients: Mapped[list["Patient"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    role_definitions: Mapped[list["RoleDefinition"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
        foreign_keys="RoleDefinition.organization_id",
    )
    invites: Mapped[list["PractitionerInvite"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
