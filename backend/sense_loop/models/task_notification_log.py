"""Task Notification Log model - audit trail for task notifications."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_50, str_255

if TYPE_CHECKING:
    from .patient import Patient
    from .patient_instruction_task import PatientInstructionTask


class TaskNotificationLog(BaseDbModel):
    """Log of task-related notifications sent to patients.

    Tracks delivery status, user responses (for confirmation notifications),
    and provides audit trail for notification history.
    """

    __tablename__ = "sl_task_notification_log"

    id: Mapped[PrimaryKey[UUID]]

    # Task and patient
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_patient_instruction_task.id", ondelete="CASCADE"),
        index=True,
    )
    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_patient.id", ondelete="CASCADE"),
        index=True,
    )

    # Notification details
    notification_type: Mapped[str_50]  # reminder, overdue, confirmation, success, daily_summary
    channel: Mapped[str_50]  # push, sms, email

    # Timing
    sent_at: Mapped[datetime]
    delivered_at: Mapped[datetime | None] = mapped_column(nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    failure_reason: Mapped[str_255 | None] = mapped_column(nullable=True)

    # Response (for confirmation notifications)
    response: Mapped[str_50 | None] = mapped_column(nullable=True)  # yes, no, snooze
    responded_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Content
    title: Mapped[str_255]
    body: Mapped[str] = mapped_column(Text)
    action_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Example action_data:
    # {
    #     "type": "task_confirmation",
    #     "task_id": "uuid",
    #     "actions": [
    #         {"id": "yes", "label": "Yes, I took it"},
    #         {"id": "no", "label": "No"},
    #         {"id": "snooze", "label": "Remind me in 30 min"}
    #     ]
    # }

    # External reference (push notification ID, etc.)
    external_id: Mapped[str_255 | None] = mapped_column(nullable=True)

    # Relationships
    task: Mapped["PatientInstructionTask"] = relationship(
        back_populates="notifications",
    )
    patient: Mapped["Patient"] = relationship(
        foreign_keys=[patient_id],
    )

    @property
    def was_delivered(self) -> bool:
        """Check if notification was delivered."""
        return self.delivered_at is not None

    @property
    def was_read(self) -> bool:
        """Check if notification was read."""
        return self.read_at is not None

    @property
    def has_response(self) -> bool:
        """Check if user responded to notification."""
        return self.response is not None
