"""Notification service - SMS, email, push notifications."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from html import escape
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from sense_loop.config import sl_settings
from sense_loop.models import Alert, Patient, Practitioner

logger = logging.getLogger(__name__)

# Firebase app singleton
_firebase_app = None

# Email provider singleton
_email_provider = None


def _get_email_provider():
    """Get email provider, lazily initialized."""
    global _email_provider

    if _email_provider is None:
        from sense_loop.services.email_providers import get_email_provider

        _email_provider = get_email_provider()
    return _email_provider


def _init_firebase():
    """Initialize Firebase Admin SDK lazily."""
    global _firebase_app

    if _firebase_app is not None:
        return _firebase_app

    try:
        import firebase_admin
        from firebase_admin import credentials

        # Check if already initialized
        try:
            _firebase_app = firebase_admin.get_app()
            return _firebase_app
        except ValueError:
            pass  # Not initialized yet

        # Initialize from credentials
        if sl_settings.firebase_credentials_path:
            cred = credentials.Certificate(sl_settings.firebase_credentials_path)
        elif sl_settings.firebase_credentials_json:
            cred_dict = json.loads(
                sl_settings.firebase_credentials_json.get_secret_value()
            )
            cred = credentials.Certificate(cred_dict)
        else:
            logger.warning("Firebase credentials not configured, push notifications disabled")
            return None

        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized")
        return _firebase_app

    except Exception as e:
        logger.error("Failed to initialize Firebase: %s", e)
        return None


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

    async def send_push(
        self,
        patient_id: UUID,
        title: str,
        body: str,
        data: dict | None = None,
    ) -> int:
        """Send push notification to a patient's registered devices.

        Args:
            patient_id: Patient UUID
            title: Notification title
            body: Notification body text
            data: Optional data payload for the app

        Returns:
            Number of devices notified
        """
        if not sl_settings.push_notifications_enabled:
            logger.debug("Push notifications disabled")
            return 0

        app = _init_firebase()
        if not app:
            logger.warning("Firebase not initialized, skipping push notification")
            return 0

        from firebase_admin import messaging
        from sense_loop.models import PatientDevice

        # Get active devices for patient
        stmt = select(PatientDevice).where(
            PatientDevice.patient_id == patient_id,
            PatientDevice.is_active == True,  # noqa: E712
        )
        devices = list(self.db.execute(stmt).scalars().all())

        if not devices:
            logger.debug("No registered devices for patient %s", patient_id)
            return 0

        # Send to each device
        success_count = 0
        for device in devices:
            try:
                message = messaging.Message(
                    notification=messaging.Notification(
                        title=title,
                        body=body,
                    ),
                    data={k: str(v) for k, v in (data or {}).items()},
                    token=device.device_token,
                    # iOS specific settings
                    apns=messaging.APNSConfig(
                        payload=messaging.APNSPayload(
                            aps=messaging.Aps(
                                sound="default",
                                badge=1,
                            ),
                        ),
                    ),
                )

                response = messaging.send(message)
                logger.info(
                    "Push notification sent to device %s: %s",
                    device.id,
                    response,
                )
                success_count += 1

                # Update last used timestamp
                device.last_used_at = datetime.utcnow()

            except messaging.UnregisteredError:
                # Token is no longer valid, mark device as inactive
                logger.warning(
                    "Device %s token is unregistered, marking inactive",
                    device.id,
                )
                device.is_active = False

            except Exception as e:
                logger.error(
                    "Failed to send push to device %s: %s",
                    device.id,
                    e,
                )

        self.db.flush()
        return success_count

    async def send_patient_notification(
        self,
        patient_id: UUID,
        title: str,
        body: str,
        data: dict | None = None,
        channel: str | None = None,
    ) -> bool:
        """Send notification to patient via configured channel.

        Args:
            patient_id: Patient UUID
            title: Notification title
            body: Notification body text
            data: Optional data payload (for push)
            channel: Override channel ("email", "sms", "push"), or None to use config

        Returns:
            True if notification was sent successfully
        """
        from sense_loop.models import Patient
        from sense_loop.services import ConfigService

        # Get patient for email/phone
        patient = self.db.get(Patient, patient_id)
        if not patient:
            logger.warning("Patient %s not found", patient_id)
            return False

        # Determine channel from config if not specified
        if not channel:
            config_service = ConfigService(self.db)
            channel = config_service.get_patient_reminder_channel(patient.organization_id)

        logger.info(
            "Sending %s notification to patient %s: %s",
            channel,
            patient_id,
            title,
        )

        if channel == "email":
            if not patient.email:
                logger.warning("Patient %s has no email address", patient_id)
                return False

            # Build deep link URL from data payload
            deep_link_url = None
            deep_link_text = "Open in App"
            if data:
                deep_link_url = self._build_deep_link_url(data)
                notification_type = data.get("type", "")
                if notification_type == "daily_summary":
                    deep_link_text = "View Today's Tasks"
                elif "task" in notification_type:
                    deep_link_text = "View Task"

            await self.send_patient_email(
                patient=patient,
                subject=title,
                body=body,
                deep_link_url=deep_link_url,
                deep_link_text=deep_link_text,
            )
            return True

        elif channel == "sms":
            if not patient.phone:
                logger.warning("Patient %s has no phone number", patient_id)
                return False
            await self._send_sms(patient.phone, f"{title}: {body}")
            return True

        elif channel == "push":
            count = await self.send_push(patient_id, title, body, data)
            return count > 0

        else:
            logger.warning("Unknown notification channel: %s", channel)
            return False

    async def send_patient_email(
        self,
        patient: "Patient",
        subject: str,
        body: str,
        deep_link_url: str | None = None,
        deep_link_text: str = "Open in App",
    ) -> None:
        """Send email to a patient.

        Args:
            patient: Patient model instance
            subject: Email subject
            body: Email body text
            deep_link_url: Optional deep link URL for "Open in App" button
            deep_link_text: Text for the deep link button
        """
        if not patient.email:
            logger.warning("Patient %s has no email address", patient.id)
            return

        # Build HTML email with branding
        html_body = self._build_patient_email_html(
            patient_name=patient.first_name,
            subject=subject,
            body=body,
            deep_link_url=deep_link_url,
            deep_link_text=deep_link_text,
        )

        await self._send_email(
            to_email=patient.email,
            subject=subject,
            body=body,
            html_body=html_body,
        )

    def _build_patient_email_html(
        self,
        patient_name: str,
        subject: str,
        body: str,
        deep_link_url: str | None = None,
        deep_link_text: str = "Open in App",
    ) -> str:
        """Build HTML email for patient notifications."""
        from html import escape

        # Build the CTA button section if deep link is provided
        cta_section = ""
        if deep_link_url:
            cta_section = f"""
                            <!-- CTA Button -->
                            <table role="presentation" cellspacing="0" cellpadding="0" style="margin: 0 auto 30px;">
                                <tr>
                                    <td style="border-radius: 6px; background-color: #7c3aed;">
                                        <a href="{escape(deep_link_url)}" target="_blank" style="display: inline-block; padding: 14px 32px; font-size: 16px; font-weight: 600; color: #ffffff; text-decoration: none;">
                                            {escape(deep_link_text)}
                                        </a>
                                    </td>
                                </tr>
                            </table>
"""

        return f"""
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
                            <h2 style="margin: 0 0 20px; font-size: 20px; font-weight: 600; color: #1a1a1a;">{escape(subject)}</h2>
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #4a4a4a;">
                                Hi {escape(patient_name)},
                            </p>
                            <p style="margin: 0 0 30px; font-size: 16px; line-height: 1.6; color: #4a4a4a;">
                                {escape(body)}
                            </p>
{cta_section}
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

    async def _send_care_team_push(
        self, alert: Alert, care_team: list[Practitioner]
    ) -> None:
        """Send push notifications to care team.

        Note: This is for practitioner/clinician devices, not patient devices.
        Currently not implemented as clinicians use the web dashboard.
        """
        # TODO: Implement push notifications for clinician mobile apps
        logger.debug("Care team push notifications not yet implemented")

    async def _send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> None:
        """Send an email via the configured email provider.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Plain text body (fallback)
            html_body: HTML body (optional, preferred if provided)
        """
        from sense_loop.services.email_providers import EmailMessage

        try:
            provider = _get_email_provider()

            message = EmailMessage(
                to_email=to_email,
                subject=subject,
                html_content=html_body or body,
                plain_content=body,
            )

            result = provider.send(message)

            if not result.success:
                logger.error("Failed to send email to %s: %s", to_email, result.error)
                raise RuntimeError(f"Email send failed: {result.error}")

        except Exception as e:
            logger.error("Failed to send email to %s: %s", to_email, e)
            raise

    async def _send_sms(self, to_phone: str, message: str) -> None:
        """Send an SMS via Twilio."""
        # TODO: Implement actual Twilio integration
        logger.info("Would send SMS to %s: %s", to_phone, message[:50])

    def _build_deep_link_url(self, data: dict) -> str | None:
        """Build deep link URL from notification data payload.

        Args:
            data: Notification data payload containing type and IDs

        Returns:
            Deep link URL or None if no deep link is applicable
        """
        base_url = sl_settings.app_deep_link_base_url
        if not base_url:
            # Default to staging API URL for deep links
            base_url = "https://wearables.staging.senselooplabs.com"

        notification_type = data.get("type", "")

        if notification_type in ("task_reminder", "task_overdue", "task_confirmation", "task_success"):
            task_id = data.get("task_id")
            if task_id:
                return f"{base_url}/task/{task_id}"

        elif notification_type == "daily_summary":
            return f"{base_url}/tasks"

        return None

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
