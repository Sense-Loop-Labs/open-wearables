"""Patient Instruction Task model - individual task instances for patients."""

from datetime import date, datetime, time
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseDbModel
from app.mappings import PrimaryKey, str_50, str_100, str_255

if TYPE_CHECKING:
    from .patient import Patient
    from .patient_instruction_plan import PatientInstructionPlan
    from .task_notification_log import TaskNotificationLog


class PatientInstructionTask(BaseDbModel):
    """Individual task instance for a patient.

    Generated from PatientInstructionPlan based on timing configurations.
    Supports auto-completion (from wearable data), manual confirmation,
    and hybrid approaches.
    """

    __tablename__ = "sl_patient_instruction_task"
    __table_args__ = (
        Index("ix_sl_task_patient_date", "patient_id", "scheduled_date"),
        Index("ix_sl_task_status_date", "status", "scheduled_date"),
        Index("ix_sl_task_pending_triggers", "status", "completion_method", "scheduled_date"),
    )

    id: Mapped[PrimaryKey[UUID]]

    # Plan and patient
    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_patient_instruction_plan.id", ondelete="CASCADE"),
        index=True,
    )
    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey("sl_patient.id", ondelete="CASCADE"),
        index=True,
    )

    # Item reference within template content
    plan_item_id: Mapped[str_100]  # ID of item within template (e.g., "daily-wound-check")
    section_id: Mapped[str_100 | None] = mapped_column(nullable=True)  # Section containing the item

    # Task identification
    task_type: Mapped[str_50]  # vital_sign, medication, activity, wound_care, monitoring, education, follow_up
    task_code: Mapped[str_100]  # bp_reading, scheduled_medication, exercise_session, etc.
    title: Mapped[str_255]
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Completion method
    completion_method: Mapped[str_50]  # auto, manual, hybrid
    data_trigger_types: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)), nullable=True
    )  # For auto: ["blood_pressure"]
    data_threshold: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # For auto with threshold: {"min_steps": 500}
    confirmation_prompt: Mapped[str_255 | None] = mapped_column(
        nullable=True
    )  # For manual/hybrid

    # Scheduling (stored in UTC)
    scheduled_date: Mapped[date] = mapped_column(index=True)
    scheduled_at: Mapped[datetime]  # UTC datetime
    scheduled_time_local: Mapped[str_50 | None] = mapped_column(
        nullable=True
    )  # "08:00" for display
    patient_timezone: Mapped[str_50]  # e.g., "America/New_York"
    time_window_minutes: Mapped[int] = mapped_column(default=60)  # ± flexibility

    # Status
    status: Mapped[str_50] = mapped_column(default="pending", index=True)
    # pending, completed, skipped, missed, cancelled

    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completion_source: Mapped[str_50 | None] = mapped_column(nullable=True)
    # auto_data, user_confirmed, user_logged, clinician_marked

    # Linked data (for auto-completed tasks)
    linked_data_type: Mapped[str_50 | None] = mapped_column(nullable=True)
    # data_point_series, event_record, questionnaire_response
    linked_data_id: Mapped[UUID | None] = mapped_column(nullable=True)
    linked_data_value: Mapped[str_255 | None] = mapped_column(nullable=True)  # "128/82 mmHg"

    # User feedback
    user_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    skip_reason: Mapped[str_255 | None] = mapped_column(nullable=True)

    # Notification tracking
    reminder_sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    overdue_notification_count: Mapped[int] = mapped_column(default=0)
    last_overdue_sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    confirmation_sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    confirmation_response_count: Mapped[int] = mapped_column(default=0)
    success_notification_sent_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Snooze tracking
    snoozed_until: Mapped[datetime | None] = mapped_column(nullable=True)
    snooze_count: Mapped[int] = mapped_column(default=0)

    # Audit
    updated_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        onupdate=datetime.utcnow,
    )

    # Relationships
    plan: Mapped["PatientInstructionPlan"] = relationship(
        back_populates="tasks",
    )
    patient: Mapped["Patient"] = relationship(
        back_populates="instruction_tasks",
    )
    notifications: Mapped[list["TaskNotificationLog"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskNotificationLog.sent_at.desc()",
    )

    @property
    def is_pending(self) -> bool:
        """Check if task is still pending."""
        return self.status == "pending"

    @property
    def is_completed(self) -> bool:
        """Check if task was completed."""
        return self.status == "completed"

    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue (past time window)."""
        if self.status != "pending":
            return False
        from datetime import timedelta

        window_end = self.scheduled_at + timedelta(minutes=self.time_window_minutes)
        return datetime.utcnow() > window_end

    @property
    def is_snoozed(self) -> bool:
        """Check if task is currently snoozed."""
        if not self.snoozed_until:
            return False
        return datetime.utcnow() < self.snoozed_until

    @property
    def can_auto_complete(self) -> bool:
        """Check if this task can be auto-completed from data."""
        return self.completion_method in ("auto", "hybrid") and bool(self.data_trigger_types)

    def matches_data_type(self, data_type: str) -> bool:
        """Check if this task can be completed by the given data type."""
        if not self.data_trigger_types:
            return False
        return data_type in self.data_trigger_types
