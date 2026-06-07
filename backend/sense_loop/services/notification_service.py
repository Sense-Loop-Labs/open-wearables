"""Notification service - SMS, email, push notifications."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from sense_loop.config import sl_settings
from sense_loop.models import Alert, Patient, Practitioner

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications."""

    def __init__(self, db: Session):
        self.db = db

    async def notify_alert(self, alert: Alert) -> list[str]:
        """Send notifications for a new alert.

        Returns list of channels notified.
        """
        channels_notified = []

        # Get patient
        patient = alert.patient
        if not patient:
            logger.warning("Alert %s has no patient", alert.id)
            return channels_notified

        # Get organization settings
        org_settings = patient.organization.settings or {}
        notification_prefs = org_settings.get("notification_preferences", {})

        # Get care team to notify
        care_team = self._get_care_team(patient.organization_id)

        # Notify based on severity
        if alert.severity == "critical":
            # Critical: notify all channels
            if notification_prefs.get("email", True):
                await self._send_care_team_email(alert, care_team)
                channels_notified.append("email")

            if notification_prefs.get("sms", True):
                await self._send_care_team_sms(alert, care_team)
                channels_notified.append("sms")

            if notification_prefs.get("push", True):
                await self._send_care_team_push(alert, care_team)
                channels_notified.append("push")

        elif alert.severity == "warning":
            # Warning: email and push only
            if notification_prefs.get("email", True):
                await self._send_care_team_email(alert, care_team)
                channels_notified.append("email")

            if notification_prefs.get("push", True):
                await self._send_care_team_push(alert, care_team)
                channels_notified.append("push")

        # Update alert with notification info
        from datetime import datetime

        alert.notification_sent_at = datetime.utcnow()
        alert.notification_channels = channels_notified
        self.db.flush()

        logger.info(
            "Sent notifications for alert %s via %s",
            alert.id,
            channels_notified,
        )

        return channels_notified

    def _get_care_team(self, organization_id: UUID) -> list[Practitioner]:
        """Get practitioners in the organization to notify."""
        from sqlalchemy import select

        from sense_loop.models import PractitionerRole

        stmt = (
            select(Practitioner)
            .join(PractitionerRole)
            .where(
                PractitionerRole.organization_id == organization_id,
                PractitionerRole.is_active == True,  # noqa: E712
                Practitioner.is_active == True,  # noqa: E712
            )
        )

        return list(self.db.execute(stmt).unique().scalars().all())

    async def _send_care_team_email(
        self, alert: Alert, care_team: list[Practitioner]
    ) -> None:
        """Send email notifications to care team."""
        if not sl_settings.sendgrid_api_key:
            logger.warning("SendGrid API key not configured, skipping email")
            return

        for practitioner in care_team:
            if not practitioner.email:
                continue

            try:
                await self._send_email(
                    to_email=practitioner.email,
                    subject=f"[{alert.severity.upper()}] {alert.title}",
                    body=self._format_alert_email(alert, practitioner),
                )
            except Exception as e:
                logger.error(
                    "Failed to send email to %s: %s",
                    practitioner.email,
                    e,
                )

    async def _send_care_team_sms(
        self, alert: Alert, care_team: list[Practitioner]
    ) -> None:
        """Send SMS notifications to care team."""
        if not sl_settings.twilio_account_sid:
            logger.warning("Twilio not configured, skipping SMS")
            return

        for practitioner in care_team:
            if not practitioner.phone:
                continue

            try:
                await self._send_sms(
                    to_phone=practitioner.phone,
                    message=self._format_alert_sms(alert),
                )
            except Exception as e:
                logger.error(
                    "Failed to send SMS to %s: %s",
                    practitioner.phone,
                    e,
                )

    async def _send_care_team_push(
        self, alert: Alert, care_team: list[Practitioner]
    ) -> None:
        """Send push notifications to care team."""
        # TODO: Implement push notifications
        # This would integrate with Firebase, OneSignal, or similar
        logger.debug("Push notifications not yet implemented")

    async def _send_email(self, to_email: str, subject: str, body: str) -> None:
        """Send an email via SendGrid."""
        # TODO: Implement actual SendGrid integration
        logger.info("Would send email to %s: %s", to_email, subject)

    async def _send_sms(self, to_phone: str, message: str) -> None:
        """Send an SMS via Twilio."""
        # TODO: Implement actual Twilio integration
        logger.info("Would send SMS to %s: %s", to_phone, message[:50])

    def _format_alert_email(self, alert: Alert, practitioner: Practitioner) -> str:
        """Format alert as email body."""
        patient = alert.patient
        return f"""
Dear {practitioner.first_name},

A {alert.severity.upper()} alert has been triggered for patient {patient.full_name}.

Alert: {alert.title}
{alert.message or ''}

Vital Type: {alert.vital_type or 'N/A'}
Observed Value: {alert.observed_value or 'N/A'}
Threshold: {alert.threshold_value or 'N/A'}

Days Post-Surgery: {alert.days_post_surgery or 'N/A'}

Please review this alert in the Sense Loop dashboard.

This is an automated notification from Sense Loop.
"""

    def _format_alert_sms(self, alert: Alert) -> str:
        """Format alert as SMS message."""
        patient = alert.patient
        return (
            f"[{alert.severity.upper()}] {alert.title} - "
            f"{patient.full_name}: {alert.vital_type}={alert.observed_value}"
        )

    async def send_invite_email(
        self,
        invite_email: str,
        invite_name: str,
        organization_name: str,
        invite_url: str,
    ) -> None:
        """Send invitation email to a new clinician."""
        subject = f"You've been invited to join {organization_name} on Sense Loop"
        body = f"""
Dear {invite_name},

You've been invited to join {organization_name} as a clinician on Sense Loop.

Click the link below to set your password and access the platform:
{invite_url}

This invitation expires in 24 hours.

If you did not expect this invitation, please ignore this email.

Best regards,
The Sense Loop Team
"""
        await self._send_email(invite_email, subject, body)

    async def send_password_reset_email(
        self,
        email: str,
        name: str,
        reset_url: str,
    ) -> None:
        """Send password reset email."""
        subject = "Reset Your Sense Loop Password"
        body = f"""
Dear {name},

We received a request to reset your password for Sense Loop.

Click the link below to set a new password:
{reset_url}

This link expires in 1 hour.

If you did not request a password reset, please ignore this email.

Best regards,
The Sense Loop Team
"""
        await self._send_email(email, subject, body)
