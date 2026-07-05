"""SendGrid email provider implementation."""

from __future__ import annotations

import logging

from pydantic import SecretStr

from .base import EmailMessage, EmailProvider, EmailResult

logger = logging.getLogger(__name__)


class SendGridProvider(EmailProvider):
    """SendGrid email provider."""

    def __init__(
        self,
        api_key: SecretStr,
        from_email: str | None = None,
        from_name: str | None = None,
    ):
        """Initialize SendGrid provider.

        Args:
            api_key: SendGrid API key.
            from_email: Default sender email address.
            from_name: Default sender name.
        """
        self.api_key = api_key
        self.default_from_email = from_email
        self.default_from_name = from_name
        self._client = None

    def _get_client(self):
        """Lazily initialize SendGrid client."""
        if self._client is None:
            from sendgrid import SendGridAPIClient

            self._client = SendGridAPIClient(self.api_key.get_secret_value())
        return self._client

    def send(self, message: EmailMessage) -> EmailResult:
        """Send an email via SendGrid.

        Args:
            message: The email message to send.

        Returns:
            EmailResult with success status.
        """
        from sendgrid.helpers.mail import Content, Email, Mail, To

        try:
            client = self._get_client()

            from_email = message.from_email or self.default_from_email
            from_name = message.from_name or self.default_from_name

            from_email_obj = Email(email=from_email, name=from_name)
            to_email_obj = To(message.to_email)

            mail = Mail(
                from_email=from_email_obj,
                to_emails=to_email_obj,
                subject=message.subject,
            )

            # Add plain text content if provided
            if message.plain_content:
                mail.add_content(Content("text/plain", message.plain_content))

            # Add HTML content
            mail.add_content(Content("text/html", message.html_content))

            response = client.send(mail)

            if 200 <= response.status_code < 300:
                # SendGrid returns message ID in headers
                message_id = response.headers.get("X-Message-Id")
                logger.info(
                    "Email sent successfully to %s (status: %s)",
                    message.to_email,
                    response.status_code,
                )
                return EmailResult(success=True, message_id=message_id)
            else:
                error_msg = f"SendGrid returned status {response.status_code}"
                logger.error(
                    "SendGrid returned non-success status %s for email to %s",
                    response.status_code,
                    message.to_email,
                )
                return EmailResult(success=False, error=error_msg)

        except Exception as e:
            logger.error("Failed to send email to %s: %s", message.to_email, e)
            return EmailResult(success=False, error=str(e))
