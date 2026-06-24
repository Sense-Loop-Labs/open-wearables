"""Settings schemas for configuration API."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationSettings(BaseModel):
    """Notification configuration settings."""

    enabled: bool = True
    patient_reminder_channel: Literal["email", "sms", "push"] = "push"
    care_team_alert_channel: Literal["email", "sms", "push", "all"] = "email"
    quiet_hours_enabled: bool = False
    quiet_hours_start: str | None = None  # "HH:MM" format
    quiet_hours_end: str | None = None  # "HH:MM" format


class AlertSettings(BaseModel):
    """Alert configuration settings."""

    auto_escalate: bool = False
    escalation_delay_minutes: int = Field(default=60, ge=5, le=1440)


class SettingsUpdate(BaseModel):
    """Request to update settings."""

    notifications: NotificationSettings | None = None
    alerts: AlertSettings | None = None


class SettingsResponse(BaseModel):
    """Settings response."""

    id: UUID
    organization_id: UUID | None
    notifications: NotificationSettings
    alerts: AlertSettings
    updated_at: datetime

    class Config:
        from_attributes = True
