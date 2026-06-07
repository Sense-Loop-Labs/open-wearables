"""Practitioner invite model - pending invitations."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_50, str_100, str_255


class PractitionerInvite(BaseDbModel):
    """Pending invitation for a clinician to join an organization."""

    __tablename__ = "sl_practitioner_invite"

    id: Mapped[PrimaryKey[UUID]]

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_organization.id", ondelete="CASCADE"),
        index=True,
    )

    # Invitee info
    email: Mapped[str_255]
    first_name: Mapped[str_100]
    last_name: Mapped[str_100]
    role_code: Mapped[str_50]  # Role to assign when accepted

    # Secure invite token (for password set URL)
    invite_secret: Mapped[str_100]  # URL-safe token
    expires_at: Mapped[datetime]  # Default: 24 hours from creation

    # Tracking
    invited_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_practitioner.id", ondelete="SET NULL"),
        nullable=True,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Email tracking
    email_sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    email_send_count: Mapped[int] = mapped_column(default=0)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="invites")
    invited_by: Mapped["Practitioner | None"] = relationship(
        foreign_keys=[invited_by_id],
    )

    @property
    def is_expired(self) -> bool:
        """Check if the invite has expired."""
        return datetime.utcnow() > self.expires_at

    @property
    def is_pending(self) -> bool:
        """Check if the invite is still pending."""
        return self.accepted_at is None and self.revoked_at is None and not self.is_expired

    @property
    def full_name(self) -> str:
        """Get invitee's full name."""
        return f"{self.first_name} {self.last_name}"
