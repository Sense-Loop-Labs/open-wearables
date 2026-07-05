"""Abstract base class for email providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EmailMessage:
    """Email message data."""

    to_email: str
    subject: str
    html_content: str
    plain_content: str | None = None
    to_name: str | None = None
    from_email: str | None = None
    from_name: str | None = None


@dataclass
class EmailResult:
    """Result of sending an email."""

    success: bool
    message_id: str | None = None
    error: str | None = None


class EmailProvider(ABC):
    """Abstract base class for email providers."""

    @abstractmethod
    def send(self, message: EmailMessage) -> EmailResult:
        """Send an email.

        Args:
            message: The email message to send.

        Returns:
            EmailResult with success status and optional message_id or error.
        """
        pass
