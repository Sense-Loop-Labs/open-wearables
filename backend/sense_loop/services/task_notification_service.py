"""Task notification service - handles sending notifications for tasks."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from sense_loop.models import (
    Patient,
    PatientInstructionTask,
    TaskNotificationLog,
)

if TYPE_CHECKING:
    from sense_loop.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


@dataclass
class NotificationConfig:
    """Configuration for task notifications."""

    reminder_lead_minutes: int = 15
    overdue_delay_minutes: int = 30
    confirmation_delay_minutes: int = 60
    max_reminders_per_task: int = 3
    daily_summary_hour: int = 8  # 8 AM local time
    enable_push: bool = True
    enable_sms: bool = False
    enable_email: bool = False


class TaskNotificationService:
    """Service for managing task notifications."""

    def __init__(
        self,
        db: Session,
        notification_service: "NotificationService | None" = None,
        config: NotificationConfig | None = None,
    ):
        self.db = db
        self.notification_service = notification_service
        self.config = config or NotificationConfig()

    async def process_pending_notifications(self) -> dict:
        """Process all pending notifications.

        Should be called periodically (e.g., every 5 minutes).

        Returns:
            Summary of notifications sent
        """
        now = datetime.utcnow()
        summary = {
            "reminders_sent": 0,
            "overdue_sent": 0,
            "confirmations_sent": 0,
        }

        # Send reminders for upcoming tasks
        reminder_count = await self._send_upcoming_reminders(now)
        summary["reminders_sent"] = reminder_count

        # Send overdue notifications
        overdue_count = await self._send_overdue_notifications(now)
        summary["overdue_sent"] = overdue_count

        # Send confirmation requests for tasks without linked data
        confirmation_count = await self._send_confirmation_requests(now)
        summary["confirmations_sent"] = confirmation_count

        return summary

    async def send_reminder(
        self,
        task: PatientInstructionTask,
        *,
        channel: str = "push",
    ) -> TaskNotificationLog | None:
        """Send a reminder notification for a task.

        Args:
            task: Task to remind about
            channel: Notification channel (push, sms, email)

        Returns:
            Notification log entry if sent, None if skipped
        """
        # Check if we've hit max reminders
        reminder_count = self._get_notification_count(task.id, "reminder")
        if reminder_count >= self.config.max_reminders_per_task:
            logger.debug(
                "Max reminders reached for task %s (%d/%d)",
                task.id,
                reminder_count,
                self.config.max_reminders_per_task,
            )
            return None

        # Check if snoozed
        if task.snoozed_until and task.snoozed_until > datetime.utcnow():
            logger.debug("Task %s is snoozed until %s", task.id, task.snoozed_until)
            return None

        # Build notification content
        title = "Task Reminder"
        body = self._build_reminder_body(task)

        # Send via notification service
        if self.notification_service:
            await self.notification_service.send_push(
                patient_id=task.patient_id,
                title=title,
                body=body,
                data={
                    "type": "task_reminder",
                    "task_id": str(task.id),
                    "plan_id": str(task.plan_id),
                },
            )

        # Log notification
        log = self._create_notification_log(
            task=task,
            notification_type="reminder",
            channel=channel,
            title=title,
            body=body,
        )

        logger.info("Sent reminder for task %s to patient %s", task.id, task.patient_id)
        return log

    async def send_overdue(
        self,
        task: PatientInstructionTask,
        *,
        channel: str = "push",
    ) -> TaskNotificationLog | None:
        """Send an overdue notification for a task.

        Args:
            task: Overdue task
            channel: Notification channel

        Returns:
            Notification log entry if sent
        """
        # Only send one overdue notification per task
        overdue_count = self._get_notification_count(task.id, "overdue")
        if overdue_count > 0:
            return None

        title = "Task Overdue"
        body = self._build_overdue_body(task)

        if self.notification_service:
            await self.notification_service.send_push(
                patient_id=task.patient_id,
                title=title,
                body=body,
                data={
                    "type": "task_overdue",
                    "task_id": str(task.id),
                },
            )

        log = self._create_notification_log(
            task=task,
            notification_type="overdue",
            channel=channel,
            title=title,
            body=body,
        )

        logger.info("Sent overdue notification for task %s", task.id)
        return log

    async def send_confirmation(
        self,
        task: PatientInstructionTask,
        *,
        channel: str = "push",
    ) -> TaskNotificationLog | None:
        """Send a confirmation request for a task.

        Used for hybrid tasks where we couldn't auto-detect completion
        and need user confirmation.

        Args:
            task: Task to confirm
            channel: Notification channel

        Returns:
            Notification log entry if sent
        """
        # Check if we've already sent a confirmation
        confirmation_count = self._get_notification_count(task.id, "confirmation")
        if confirmation_count > 0:
            return None

        prompt = task.confirmation_prompt or f"Did you complete: {task.title}?"

        title = "Task Confirmation"
        body = prompt

        if self.notification_service:
            await self.notification_service.send_push(
                patient_id=task.patient_id,
                title=title,
                body=body,
                data={
                    "type": "task_confirmation",
                    "task_id": str(task.id),
                    "actions": ["yes", "no", "snooze"],
                },
            )

        log = self._create_notification_log(
            task=task,
            notification_type="confirmation",
            channel=channel,
            title=title,
            body=body,
        )

        logger.info("Sent confirmation request for task %s", task.id)
        return log

    async def send_success(
        self,
        task: PatientInstructionTask,
        data_value: str | None = None,
        *,
        channel: str = "push",
    ) -> TaskNotificationLog | None:
        """Send a success notification when task is auto-completed.

        Args:
            task: Completed task
            data_value: Formatted value that triggered completion
            channel: Notification channel

        Returns:
            Notification log entry if sent
        """
        title = "Task Completed"
        body = self._build_success_body(task, data_value)

        if self.notification_service:
            await self.notification_service.send_push(
                patient_id=task.patient_id,
                title=title,
                body=body,
                data={
                    "type": "task_success",
                    "task_id": str(task.id),
                },
            )

        log = self._create_notification_log(
            task=task,
            notification_type="success",
            channel=channel,
            title=title,
            body=body,
        )

        logger.info("Sent success notification for task %s", task.id)
        return log

    async def send_daily_summary(
        self,
        patient_id: UUID,
        tasks: list[PatientInstructionTask],
        *,
        channel: str = "push",
    ) -> TaskNotificationLog | None:
        """Send a daily summary of tasks.

        Args:
            patient_id: Patient to notify
            tasks: Today's tasks
            channel: Notification channel

        Returns:
            Notification log entry if sent
        """
        if not tasks:
            return None

        title = "Today's Tasks"
        body = self._build_daily_summary_body(tasks)

        if self.notification_service:
            await self.notification_service.send_push(
                patient_id=patient_id,
                title=title,
                body=body,
                data={
                    "type": "daily_summary",
                    "task_count": len(tasks),
                },
            )

        # Log against first task (or create a summary-type log)
        log = TaskNotificationLog(
            id=uuid4(),
            task_id=tasks[0].id,
            patient_id=patient_id,
            notification_type="daily_summary",
            channel=channel,
            title=title,
            body=body,
            sent_at=datetime.utcnow(),
        )
        self.db.add(log)
        self.db.flush()

        logger.info(
            "Sent daily summary to patient %s with %d tasks",
            patient_id,
            len(tasks),
        )
        return log

    def record_response(
        self,
        notification_log: TaskNotificationLog,
        response: str,
    ) -> TaskNotificationLog:
        """Record user response to a notification.

        Args:
            notification_log: The notification being responded to
            response: User response (yes, no, snooze)

        Returns:
            Updated notification log
        """
        notification_log.response = response
        notification_log.responded_at = datetime.utcnow()
        self.db.flush()

        logger.info(
            "Recorded response '%s' for notification %s",
            response,
            notification_log.id,
        )
        return notification_log

    async def _send_upcoming_reminders(self, now: datetime) -> int:
        """Send reminders for tasks coming up soon."""
        reminder_window = now + timedelta(minutes=self.config.reminder_lead_minutes)

        # Find pending tasks scheduled within the reminder window
        stmt = select(PatientInstructionTask).where(
            PatientInstructionTask.status == "pending",
            PatientInstructionTask.scheduled_at <= reminder_window,
            PatientInstructionTask.scheduled_at > now,
            or_(
                PatientInstructionTask.snoozed_until.is_(None),
                PatientInstructionTask.snoozed_until <= now,
            ),
        )

        tasks = list(self.db.execute(stmt).scalars().all())

        count = 0
        for task in tasks:
            result = await self.send_reminder(task)
            if result:
                count += 1

        return count

    async def _send_overdue_notifications(self, now: datetime) -> int:
        """Send notifications for overdue tasks."""
        overdue_threshold = now - timedelta(minutes=self.config.overdue_delay_minutes)

        # Find pending tasks that are past their scheduled time
        stmt = select(PatientInstructionTask).where(
            PatientInstructionTask.status == "pending",
            PatientInstructionTask.scheduled_at < overdue_threshold,
        )

        tasks = list(self.db.execute(stmt).scalars().all())

        count = 0
        for task in tasks:
            result = await self.send_overdue(task)
            if result:
                count += 1

        return count

    async def _send_confirmation_requests(self, now: datetime) -> int:
        """Send confirmation requests for hybrid tasks."""
        confirmation_threshold = now - timedelta(
            minutes=self.config.confirmation_delay_minutes
        )

        # Find pending hybrid tasks past their scheduled time
        # that don't have linked data (not auto-completed)
        stmt = select(PatientInstructionTask).where(
            PatientInstructionTask.status == "pending",
            PatientInstructionTask.completion_method == "hybrid",
            PatientInstructionTask.scheduled_at < confirmation_threshold,
            PatientInstructionTask.linked_data_id.is_(None),
        )

        tasks = list(self.db.execute(stmt).scalars().all())

        count = 0
        for task in tasks:
            result = await self.send_confirmation(task)
            if result:
                count += 1

        return count

    def _get_notification_count(self, task_id: UUID, notification_type: str) -> int:
        """Get count of notifications of a type for a task."""
        stmt = select(TaskNotificationLog).where(
            TaskNotificationLog.task_id == task_id,
            TaskNotificationLog.notification_type == notification_type,
        )
        return len(list(self.db.execute(stmt).scalars().all()))

    def _create_notification_log(
        self,
        task: PatientInstructionTask,
        notification_type: str,
        channel: str,
        title: str,
        body: str,
    ) -> TaskNotificationLog:
        """Create a notification log entry."""
        log = TaskNotificationLog(
            id=uuid4(),
            task_id=task.id,
            patient_id=task.patient_id,
            notification_type=notification_type,
            channel=channel,
            title=title,
            body=body,
            sent_at=datetime.utcnow(),
        )
        self.db.add(log)
        self.db.flush()
        return log

    def _build_reminder_body(self, task: PatientInstructionTask) -> str:
        """Build reminder notification body."""
        time_str = task.scheduled_time_local or "now"
        return f"{task.title} is scheduled for {time_str}"

    def _build_overdue_body(self, task: PatientInstructionTask) -> str:
        """Build overdue notification body."""
        return f"You have an overdue task: {task.title}"

    def _build_success_body(
        self,
        task: PatientInstructionTask,
        data_value: str | None,
    ) -> str:
        """Build success notification body."""
        if data_value:
            return f"Great job! {task.title} completed with reading: {data_value}"
        return f"Great job! {task.title} has been marked complete."

    def _build_daily_summary_body(
        self, tasks: list[PatientInstructionTask]
    ) -> str:
        """Build daily summary notification body."""
        if len(tasks) == 1:
            return f"You have 1 task today: {tasks[0].title}"

        task_titles = [t.title for t in tasks[:3]]
        summary = ", ".join(task_titles)

        if len(tasks) > 3:
            return f"You have {len(tasks)} tasks today: {summary}, and more..."

        return f"You have {len(tasks)} tasks today: {summary}"
