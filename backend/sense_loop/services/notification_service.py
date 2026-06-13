"""Notification service - SMS, email, push notifications."""

from __future__ import annotations

import logging
from html import escape
from uuid import UUID

from sqlalchemy.orm import Session

from sense_loop.config import sl_settings
from sense_loop.models import Alert, Patient, Practitioner

logger = logging.getLogger(__name__)


def _get_sendgrid_client():
    """Get SendGrid client, lazily imported."""
    from sendgrid import SendGridAPIClient

    return SendGridAPIClient(sl_settings.sendgrid_api_key.get_secret_value())


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

    async def _send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> None:
        """Send an email via SendGrid.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Plain text body (fallback)
            html_body: HTML body (optional, preferred if provided)
        """
        if not sl_settings.sendgrid_api_key:
            logger.warning("SendGrid API key not configured, skipping email to %s", to_email)
            return

        from sendgrid.helpers.mail import Email, Content, Mail, To

        try:
            sg = _get_sendgrid_client()

            from_email = Email(
                email=sl_settings.notification_from_email,
                name=sl_settings.notification_from_name,
            )
            to_email_obj = To(to_email)

            # Build message with both plain text and HTML
            message = Mail(
                from_email=from_email,
                to_emails=to_email_obj,
                subject=subject,
            )

            # Add plain text content
            message.add_content(Content("text/plain", body))

            # Add HTML content if provided
            if html_body:
                message.add_content(Content("text/html", html_body))

            response = sg.send(message)

            if response.status_code >= 200 and response.status_code < 300:
                logger.info(
                    "Email sent successfully to %s (status: %s)",
                    to_email,
                    response.status_code,
                )
            else:
                logger.error(
                    "SendGrid returned non-success status %s for email to %s",
                    response.status_code,
                    to_email,
                )

        except Exception as e:
            logger.error("Failed to send email to %s: %s", to_email, e)
            raise

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

        # Plain text version (fallback)
        body = f"""
Dear {invite_name},

You've been invited to join {organization_name} as a clinician on Sense Loop.

Click the link below to set your password and access the platform:
{invite_url}

This invitation expires in {sl_settings.invite_expire_hours} hours.

If you did not expect this invitation, please ignore this email.

Best regards,
The Sense Loop Team
"""

        # HTML version (preferred)
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f5f5f5;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 600px; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center; border-bottom: 1px solid #eee;">
                            <h1 style="margin: 0; font-size: 24px; font-weight: 600; color: #7c3aed;">Sense Loop</h1>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <h2 style="margin: 0 0 20px; font-size: 20px; font-weight: 600; color: #1a1a1a;">You're Invited!</h2>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #4a4a4a;">
                                Dear {escape(invite_name)},
                            </p>
                            <p style="margin: 0 0 30px; font-size: 16px; line-height: 1.6; color: #4a4a4a;">
                                You've been invited to join <strong>{escape(organization_name)}</strong> as a clinician on Sense Loop.
                            </p>
                            <!-- CTA Button -->
                            <table role="presentation" cellspacing="0" cellpadding="0" style="margin: 0 auto 30px;">
                                <tr>
                                    <td style="border-radius: 6px; background-color: #7c3aed;">
                                        <a href="{escape(invite_url)}" target="_blank" style="display: inline-block; padding: 14px 32px; font-size: 16px; font-weight: 600; color: #ffffff; text-decoration: none;">
                                            Accept Invitation
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 0 0 10px; font-size: 14px; line-height: 1.6; color: #6b6b6b;">
                                This invitation expires in {sl_settings.invite_expire_hours} hours.
                            </p>
                            <p style="margin: 0; font-size: 14px; line-height: 1.6; color: #6b6b6b;">
                                If you did not expect this invitation, you can safely ignore this email.
                            </p>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 40px; background-color: #fafafa; border-top: 1px solid #eee; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; font-size: 12px; color: #888; text-align: center;">
                                &copy; Sense Loop Labs &bull; Clinical Remote Patient Monitoring
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

        await self._send_email(invite_email, subject, body, html_body)

    async def send_password_reset_email(
        self,
        email: str,
        name: str,
        reset_url: str,
    ) -> None:
        """Send password reset email."""
        subject = "Reset Your Sense Loop Password"

        # Plain text version
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

        # HTML version
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f5f5f5;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 600px; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center; border-bottom: 1px solid #eee;">
                            <h1 style="margin: 0; font-size: 24px; font-weight: 600; color: #7c3aed;">Sense Loop</h1>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <h2 style="margin: 0 0 20px; font-size: 20px; font-weight: 600; color: #1a1a1a;">Reset Your Password</h2>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #4a4a4a;">
                                Dear {escape(name)},
                            </p>
                            <p style="margin: 0 0 30px; font-size: 16px; line-height: 1.6; color: #4a4a4a;">
                                We received a request to reset your password for Sense Loop. Click the button below to set a new password.
                            </p>
                            <!-- CTA Button -->
                            <table role="presentation" cellspacing="0" cellpadding="0" style="margin: 0 auto 30px;">
                                <tr>
                                    <td style="border-radius: 6px; background-color: #7c3aed;">
                                        <a href="{escape(reset_url)}" target="_blank" style="display: inline-block; padding: 14px 32px; font-size: 16px; font-weight: 600; color: #ffffff; text-decoration: none;">
                                            Reset Password
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin: 0 0 10px; font-size: 14px; line-height: 1.6; color: #6b6b6b;">
                                This link expires in 1 hour.
                            </p>
                            <p style="margin: 0; font-size: 14px; line-height: 1.6; color: #6b6b6b;">
                                If you did not request a password reset, you can safely ignore this email.
                            </p>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 40px; background-color: #fafafa; border-top: 1px solid #eee; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; font-size: 12px; color: #888; text-align: center;">
                                &copy; Sense Loop Labs &bull; Clinical Remote Patient Monitoring
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

        await self._send_email(email, subject, body, html_body)
