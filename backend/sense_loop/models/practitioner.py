"""Practitioner model - clinical staff with their own auth system."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, Unique, str_50, str_100, str_255


class Practitioner(BaseDbModel):
    """Clinical staff member.

    Practitioners have their own auth system independent from OW Developer.
    This keeps the extension cleanly separated for upstream OW merges.
    """

    __tablename__ = "sl_practitioner"

    id: Mapped[PrimaryKey[UUID]]

    # Own authentication (independent from OW developer table)
    email: Mapped[Unique[str_255]]
    password_hash: Mapped[str_255 | None] = mapped_column(nullable=True)  # Set when invite accepted

    # Profile
    first_name: Mapped[str_100]
    last_name: Mapped[str_100]
    phone: Mapped[str_50 | None] = mapped_column(nullable=True)

    # Professional info
    npi_number: Mapped[str_50 | None] = mapped_column(nullable=True)  # National Provider Identifier
    credentials: Mapped[str_100 | None] = mapped_column(nullable=True)  # MD, DO, PA-C, NP, RN, etc.

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Password reset
    password_reset_token: Mapped[str_255 | None] = mapped_column(nullable=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    practitioner_roles: Mapped[list["PractitionerRole"]] = relationship(
        back_populates="practitioner",
        cascade="all, delete-orphan",
    )

    @property
    def full_name(self) -> str:
        """Get practitioner's full name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def display_name(self) -> str:
        """Get practitioner's display name with credentials."""
        if self.credentials:
            return f"{self.full_name}, {self.credentials}"
        return self.full_name

    @property
    def is_password_set(self) -> bool:
        """Check if practitioner has set their password."""
        return self.password_hash is not None
