"""AWS SES email provider implementation."""

from __future__ import annotations

import logging

from .base import EmailMessage, EmailProvider, EmailResult

logger = logging.getLogger(__name__)


class SESProvider(EmailProvider):
    """AWS SES email provider."""

    def __init__(
        self,
        region: str = "us-east-1",
        from_email: str | None = None,
        from_name: str | None = None,
    ):
        """Initialize SES provider.

        Args:
            region: AWS region for SES.
            from_email: Default sender email address.
            from_name: Default sender name.
        """
        self.region = region
        self.default_from_email = from_email
        self.default_from_name = from_name
        self._client = None

    def _get_client(self):
        """Lazily initialize SES client."""
        if self._client is None:
            import boto3

            self._client = boto3.client("ses", region_name=self.region)
        return self._client

    def send(self, message: EmailMessage) -> EmailResult:
        """Send an email via AWS SES.

        Args:
            message: The email message to send.

        Returns:
            EmailResult with success status.
        """
        from botocore.exceptions import ClientError

        from_email = message.from_email or self.default_from_email
        from_name = message.from_name or self.default_from_name

        # Format source with name if provided
        if from_name:
            source = f"{from_name} <{from_email}>"
        else:
            source = from_email

        # Format destination with name if provided
        if message.to_name:
            destination = f"{message.to_name} <{message.to_email}>"
        else:
            destination = message.to_email

        try:
            client = self._get_client()

            # Build message body
            body = {"Html": {"Data": message.html_content, "Charset": "UTF-8"}}

            # Add plain text if provided
            if message.plain_content:
                body["Text"] = {"Data": message.plain_content, "Charset": "UTF-8"}

            response = client.send_email(
                Source=source,
                Destination={"ToAddresses": [destination]},
                Message={
                    "Subject": {"Data": message.subject, "Charset": "UTF-8"},
                    "Body": body,
                },
            )

            message_id = response.get("MessageId")
            logger.info(
                "Email sent successfully to %s (message_id: %s)",
                message.to_email,
                message_id,
            )
            return EmailResult(success=True, message_id=message_id)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(
                "SES error sending email to %s: [%s] %s",
                message.to_email,
                error_code,
                error_message,
            )
            return EmailResult(success=False, error=f"[{error_code}] {error_message}")

        except Exception as e:
            logger.error("Failed to send email to %s: %s", message.to_email, e)
            return EmailResult(success=False, error=str(e))
