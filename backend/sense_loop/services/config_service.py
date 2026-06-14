"""Configuration service for retrieving system settings."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from sense_loop.models import SystemConfig


# Default settings
DEFAULTS = {
    "notifications": {
        "enabled": True,
        "patient_reminder_channel": "email",
        "care_team_alert_channel": "email",
        "quiet_hours_enabled": False,
    },
    "alerts": {
        "auto_escalate": False,
        "escalation_delay_minutes": 60,
    },
}


class ConfigService:
    """Service for managing system configuration."""

    def __init__(self, db: Session):
        self.db = db

    def get_config(self, organization_id: UUID | None = None) -> SystemConfig:
        """Get config for an organization.

        Falls back to global config if no org-specific config exists.

        Args:
            organization_id: Organization UUID, or None for global config

        Returns:
            SystemConfig (org-specific if exists, otherwise global)
        """
        if organization_id:
            # Try org-specific first
            stmt = select(SystemConfig).where(
                SystemConfig.organization_id == organization_id
            )
            config = self.db.execute(stmt).scalar_one_or_none()
            if config:
                return config

        # Fall back to global config (organization_id IS NULL)
        stmt = select(SystemConfig).where(
            SystemConfig.organization_id.is_(None)
        )
        config = self.db.execute(stmt).scalar_one_or_none()

        if not config:
            # Create default global config if missing
            config = SystemConfig(settings=DEFAULTS)
            self.db.add(config)
            self.db.flush()

        return config

    def get(
        self,
        key: str,
        organization_id: UUID | None = None,
        default=None,
    ):
        """Get a setting value by dot-notation key.

        Args:
            key: Setting key (e.g., "notifications.patient_reminder_channel")
            organization_id: Organization UUID for org-specific settings
            default: Default value if not found

        Returns:
            Setting value or default
        """
        config = self.get_config(organization_id)
        value = config.get(key)

        # Fall back to defaults if not set
        if value is None:
            value = self._get_default(key)

        return value if value is not None else default

    def set(
        self,
        key: str,
        value,
        organization_id: UUID | None = None,
    ) -> SystemConfig:
        """Set a setting value.

        Args:
            key: Setting key (e.g., "notifications.patient_reminder_channel")
            value: Value to set
            organization_id: Organization UUID for org-specific settings

        Returns:
            Updated SystemConfig
        """
        config = self.get_config(organization_id)
        config.set(key, value)
        self.db.flush()
        return config

    def get_patient_reminder_channel(
        self, organization_id: UUID | None = None
    ) -> str:
        """Get the notification channel for patient reminders.

        Args:
            organization_id: Organization UUID

        Returns:
            Channel name: "email", "sms", or "push"
        """
        return self.get(
            "notifications.patient_reminder_channel",
            organization_id,
            default="email",
        )

    def get_care_team_alert_channel(
        self, organization_id: UUID | None = None
    ) -> str:
        """Get the notification channel for care team alerts.

        Args:
            organization_id: Organization UUID

        Returns:
            Channel name: "email", "sms", "push", or "all"
        """
        return self.get(
            "notifications.care_team_alert_channel",
            organization_id,
            default="email",
        )

    def are_notifications_enabled(
        self, organization_id: UUID | None = None
    ) -> bool:
        """Check if notifications are enabled.

        Args:
            organization_id: Organization UUID

        Returns:
            True if notifications are enabled, False otherwise
        """
        return self.get(
            "notifications.enabled",
            organization_id,
            default=True,
        )

    def _get_default(self, key: str):
        """Get default value for a setting key."""
        keys = key.split(".")
        value = DEFAULTS
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None
        return value
