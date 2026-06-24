"""System configuration model."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm.attributes import flag_modified

from app.database import BaseDbModel
from app.mappings import PrimaryKey

if TYPE_CHECKING:
    from sense_loop.models import Organization


class SystemConfig(BaseDbModel):
    """System-wide configuration.

    Can be global (organization_id = None) or per-organization.
    Organization-specific settings override global defaults.

    Settings are stored in a JSONB column for flexibility.
    Common settings include:
    - notifications.patient_reminder_channel: "email" | "sms" | "push"
    - notifications.care_team_alert_channel: "email" | "sms" | "push" | "all"
    - notifications.quiet_hours_enabled: bool
    - notifications.quiet_hours_start: "HH:MM"
    - notifications.quiet_hours_end: "HH:MM"
    - alerts.auto_escalate: bool
    - alerts.escalation_delay_minutes: int
    """

    __tablename__ = "sl_system_config"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_system_config_org"),
    )

    id: Mapped[PrimaryKey[UUID]]

    # None = global default, otherwise org-specific override
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sl_organization.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # All settings stored as JSONB for flexibility
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    organization: Mapped["Organization | None"] = relationship()

    def get(self, key: str, default=None):
        """Get a setting by dot-notation key.

        Example: config.get("notifications.patient_reminder_channel", "email")
        """
        keys = key.split(".")
        value = self.settings
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, key: str, value) -> None:
        """Set a setting by dot-notation key.

        Example: config.set("notifications.patient_reminder_channel", "push")
        """
        keys = key.split(".")
        settings = self.settings or {}

        # Navigate to parent, creating dicts as needed
        current = settings
        for k in keys[:-1]:
            if k not in current or not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]

        # Set the value
        current[keys[-1]] = value
        self.settings = settings
        # Flag the JSONB column as modified so SQLAlchemy detects the change
        flag_modified(self, "settings")

    def __repr__(self) -> str:
        org = f"org={self.organization_id}" if self.organization_id else "global"
        return f"<SystemConfig({org})>"
