"""Sense Loop specific configuration settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class SenseLoopSettings(BaseSettings):
    """Sense Loop extension settings."""

    model_config = SettingsConfigDict(
        env_prefix="SL_",
        extra="ignore",
    )

    # Feature flag to enable/disable the extension
    enabled: bool = True

    # Enrollment settings
    activation_code_length: int = 8
    activation_code_expire_hours: int = 72

    # Practitioner invite settings
    invite_expire_hours: int = 24
    password_min_length: int = 12

    # Alert settings
    alert_check_interval_seconds: int = 60
    alert_notification_delay_seconds: int = 300  # 5 minutes

    # Patient summary update settings
    summary_update_interval_seconds: int = 300  # 5 minutes

    # FHIR export settings
    fhir_export_batch_size: int = 100

    # Notification settings (SendGrid)
    sendgrid_api_key: SecretStr | None = None
    notification_from_email: str = "noreply@senselooplabs.com"
    notification_from_name: str = "Sense Loop"

    # SMS settings (Twilio)
    twilio_account_sid: str | None = None
    twilio_auth_token: SecretStr | None = None
    twilio_from_number: str | None = None

    # Default alert thresholds
    default_hr_high_critical: int = 120
    default_hr_high_warning: int = 100
    default_hr_low_critical: int = 40
    default_hr_low_warning: int = 50

    default_spo2_low_critical: int = 88
    default_spo2_low_warning: int = 92

    default_temp_high_critical: float = 39.0
    default_temp_high_warning: float = 38.0
    default_temp_low_critical: float = 35.0
    default_temp_low_warning: float = 36.0

    # Cedar Authorization Settings
    # Use Cedar-based authorization (parallel mode runs both and logs discrepancies)
    use_cedar_auth: bool = False
    # Run Cedar in parallel with legacy RBAC and log decision differences
    cedar_parallel_mode: bool = True
    # Cache TTL for Cedar policy evaluations (seconds)
    cedar_cache_ttl_seconds: int = 300


@lru_cache
def get_sl_settings() -> SenseLoopSettings:
    """Get cached Sense Loop settings instance."""
    return SenseLoopSettings()


sl_settings = get_sl_settings()
