"""Email provider abstraction layer.

Supports multiple email backends (SendGrid, SES) with a unified interface.
Provider selection is controlled via the EMAIL_PROVIDER config setting.
"""

from __future__ import annotations

from .base import EmailMessage, EmailProvider, EmailResult

__all__ = [
    "EmailMessage",
    "EmailProvider",
    "EmailResult",
    "get_email_provider",
]


def get_email_provider() -> EmailProvider:
    """Get the configured email provider instance.

    Returns:
        EmailProvider instance based on configuration.

    Raises:
        ValueError: If the configured provider is unknown.
        ValueError: If required configuration is missing for the provider.
    """
    from sense_loop.config import sl_settings

    provider = sl_settings.email_provider

    if provider == "sendgrid":
        if not sl_settings.sendgrid_api_key:
            raise ValueError("SendGrid API key not configured (SL_SENDGRID_API_KEY)")

        from .sendgrid_provider import SendGridProvider

        return SendGridProvider(
            api_key=sl_settings.sendgrid_api_key,
            from_email=sl_settings.notification_from_email,
            from_name=sl_settings.notification_from_name,
        )

    elif provider == "ses":
        from .ses_provider import SESProvider

        return SESProvider(
            region=sl_settings.ses_region,
            from_email=sl_settings.notification_from_email,
            from_name=sl_settings.notification_from_name,
        )

    else:
        raise ValueError(f"Unknown email provider: {provider}")
