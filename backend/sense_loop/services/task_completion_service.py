"""Task completion service - handles task completion (auto and manual)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from sense_loop.models import Patient, PatientInstructionTask

if TYPE_CHECKING:
    from sense_loop.services.task_notification_service import TaskNotificationService

logger = logging.getLogger(__name__)


class TaskCompletionService:
    """Service for managing task completion."""

    def __init__(
        self,
        db: Session,
        notification_service: "TaskNotificationService | None" = None,
    ):
        self.db = db
        self.notification_service = notification_service

    async def on_data_received(
        self,
        patient_id: UUID,
        data_type: str,
        data_id: UUID,
        data_value: Any,
        timestamp: datetime,
    ) -> list[PatientInstructionTask]:
        """Called when health data is received from wearable/device.

        Finds matching pending tasks and marks them complete.

        Args:
            patient_id: Patient who generated the data
            data_type: Type of data (e.g., "blood_pressure", "heart_rate")
            data_id: ID of the data record
            data_value: The data value (dict for BP, number for others)
            timestamp: When the data was recorded

        Returns:
            List of tasks that were completed
        """
        # Find matching pending tasks
        matching_tasks = self._find_matching_tasks(patient_id, data_type, timestamp)

        completed_tasks = []
        for task in matching_tasks:
            # Check if within time window
            if not self._is_within_time_window(task, timestamp):
                continue

            # Check threshold if applicable
            if task.data_threshold and not self._check_threshold(task, data_value):
                continue

            # Complete the task
            task.status = "completed"
            task.completed_at = timestamp
            task.completion_source = "auto_data"
            task.linked_data_type = "data_point_series"
            task.linked_data_id = data_id
            task.linked_data_value = self._format_data_value(data_type, data_value)
            task.updated_at = datetime.now(timezone.utc)

            completed_tasks.append(task)

            logger.info(
                "Auto-completed task %s from %s data for patient %s",
                task.id,
                data_type,
                patient_id,
            )

            # Send success notification if configured
            if self.notification_service:
                await self.notification_service.send_success(
                    task, task.linked_data_value
                )

        self.db.flush()
        return completed_tasks

    async def on_questionnaire_submitted(
        self,
        patient_id: UUID,
        questionnaire_code: str,
        response_id: UUID,
        submitted_at: datetime,
    ) -> list[PatientInstructionTask]:
        """Called when a questionnaire is submitted.

        Args:
            patient_id: Patient who submitted
            questionnaire_code: Code of the questionnaire
            response_id: ID of the response record
            submitted_at: When submitted

        Returns:
            List of completed tasks
        """
        # Find matching tasks (monitoring type with questionnaire trigger)
        matching_tasks = self._find_matching_tasks(
            patient_id, "questionnaire_response", submitted_at
        )

        completed_tasks = []
        for task in matching_tasks:
            if not self._is_within_time_window(task, submitted_at):
                continue

            task.status = "completed"
            task.completed_at = submitted_at
            task.completion_source = "auto_data"
            task.linked_data_type = "questionnaire_response"
            task.linked_data_id = response_id
            task.linked_data_value = f"Questionnaire: {questionnaire_code}"
            task.updated_at = datetime.now(timezone.utc)

            completed_tasks.append(task)

            logger.info(
                "Completed task %s from questionnaire submission for patient %s",
                task.id,
                patient_id,
            )

        self.db.flush()
        return completed_tasks

    def complete_task_manually(
        self,
        task: PatientInstructionTask,
        *,
        notes: str | None = None,
        completed_by: str = "user",
    ) -> PatientInstructionTask:
        """Manually mark a task as complete.

        Args:
            task: Task to complete
            notes: Optional user notes
            completed_by: Who completed it (user, clinician)

        Returns:
            Updated task
        """
        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)
        task.completion_source = f"{completed_by}_confirmed"
        task.user_notes = notes
        task.updated_at = datetime.now(timezone.utc)

        self.db.flush()

        logger.info("Manually completed task %s", task.id)
        return task

    def skip_task(
        self,
        task: PatientInstructionTask,
        *,
        reason: str | None = None,
    ) -> PatientInstructionTask:
        """Skip a task.

        Args:
            task: Task to skip
            reason: Optional reason for skipping

        Returns:
            Updated task
        """
        task.status = "skipped"
        task.skip_reason = reason
        task.updated_at = datetime.now(timezone.utc)

        self.db.flush()

        logger.info("Skipped task %s: %s", task.id, reason or "no reason")
        return task

    def snooze_task(
        self,
        task: PatientInstructionTask,
        *,
        snooze_minutes: int = 30,
    ) -> PatientInstructionTask:
        """Snooze a task reminder.

        Args:
            task: Task to snooze
            snooze_minutes: How long to snooze

        Returns:
            Updated task
        """
        task.snoozed_until = datetime.now(timezone.utc) + timedelta(minutes=snooze_minutes)
        task.snooze_count += 1
        task.updated_at = datetime.now(timezone.utc)

        self.db.flush()

        logger.info("Snoozed task %s for %d minutes", task.id, snooze_minutes)
        return task

    async def handle_confirmation_response(
        self,
        task: PatientInstructionTask,
        response: str,
        *,
        notes: str | None = None,
    ) -> PatientInstructionTask:
        """Handle response to a confirmation notification.

        Args:
            task: Task being confirmed
            response: User response (yes, no, snooze)
            notes: Optional user notes

        Returns:
            Updated task
        """
        task.confirmation_response_count += 1

        if response == "yes":
            return self.complete_task_manually(task, notes=notes, completed_by="user")
        elif response == "no":
            return self.skip_task(task, reason=notes or "User indicated not completed")
        elif response == "snooze":
            return self.snooze_task(task)
        else:
            logger.warning("Unknown confirmation response: %s", response)
            return task

    def mark_overdue_tasks(self) -> int:
        """Mark tasks as missed after time window expires.

        Should be called periodically (e.g., every 15 minutes).

        Returns:
            Number of tasks marked as missed
        """
        now = datetime.now(timezone.utc)
        today = date.today()

        # Find pending tasks that are past their window
        stmt = select(PatientInstructionTask).where(
            PatientInstructionTask.status == "pending",
            PatientInstructionTask.scheduled_date <= today,
        )

        tasks = list(self.db.execute(stmt).scalars().all())

        missed_count = 0
        for task in tasks:
            # Calculate window end
            window_end = task.scheduled_at + timedelta(minutes=task.time_window_minutes)

            # Check if past window (with some buffer)
            if now > window_end + timedelta(hours=2):  # 2 hour grace period
                task.status = "missed"
                task.updated_at = now
                missed_count += 1

        self.db.flush()

        if missed_count > 0:
            logger.info("Marked %d tasks as missed", missed_count)

        return missed_count

    def get_patient_tasks_for_date(
        self,
        patient_id: UUID,
        target_date: date,
    ) -> list[PatientInstructionTask]:
        """Get all tasks for a patient on a specific date."""
        stmt = (
            select(PatientInstructionTask)
            .where(
                PatientInstructionTask.patient_id == patient_id,
                PatientInstructionTask.scheduled_date == target_date,
                PatientInstructionTask.status != "cancelled",
            )
            .order_by(PatientInstructionTask.scheduled_at)
        )

        return list(self.db.execute(stmt).scalars().all())

    def get_pending_tasks_for_patient(
        self,
        patient_id: UUID,
        *,
        include_snoozed: bool = True,
    ) -> list[PatientInstructionTask]:
        """Get all pending tasks for a patient."""
        conditions = [
            PatientInstructionTask.patient_id == patient_id,
            PatientInstructionTask.status == "pending",
        ]

        if not include_snoozed:
            conditions.append(
                or_(
                    PatientInstructionTask.snoozed_until.is_(None),
                    PatientInstructionTask.snoozed_until <= datetime.now(timezone.utc),
                )
            )

        stmt = (
            select(PatientInstructionTask)
            .where(*conditions)
            .order_by(PatientInstructionTask.scheduled_at)
        )

        return list(self.db.execute(stmt).scalars().all())

    def _find_matching_tasks(
        self,
        patient_id: UUID,
        data_type: str,
        timestamp: datetime,
    ) -> list[PatientInstructionTask]:
        """Find pending tasks that match the data type."""
        # Look for tasks scheduled on the same day
        target_date = timestamp.date()

        stmt = select(PatientInstructionTask).where(
            PatientInstructionTask.patient_id == patient_id,
            PatientInstructionTask.status == "pending",
            PatientInstructionTask.scheduled_date == target_date,
            PatientInstructionTask.completion_method.in_(["auto", "hybrid"]),
            PatientInstructionTask.data_trigger_types.contains([data_type]),
        )

        return list(self.db.execute(stmt).scalars().all())

    def _is_within_time_window(
        self,
        task: PatientInstructionTask,
        timestamp: datetime,
    ) -> bool:
        """Check if timestamp falls within task's acceptable time window."""
        if task.scheduled_time_local is None:
            # Anytime that day is acceptable
            return timestamp.date() == task.scheduled_date

        window = timedelta(minutes=task.time_window_minutes)
        window_start = task.scheduled_at - window
        window_end = task.scheduled_at + window

        return window_start <= timestamp <= window_end

    def _check_threshold(
        self,
        task: PatientInstructionTask,
        data_value: Any,
    ) -> bool:
        """Check if data value meets task's threshold requirements."""
        threshold = task.data_threshold
        if not threshold:
            return True

        # Handle common threshold types
        if "min_steps" in threshold:
            steps = data_value if isinstance(data_value, (int, float)) else 0
            return steps >= threshold["min_steps"]

        if "min_active_minutes" in threshold:
            minutes = data_value if isinstance(data_value, (int, float)) else 0
            return minutes >= threshold["min_active_minutes"]

        # Default: no threshold check fails
        return True

    def _format_data_value(self, data_type: str, data_value: Any) -> str:
        """Format data value for display."""
        if data_type == "blood_pressure":
            if isinstance(data_value, dict):
                systolic = data_value.get("systolic", "?")
                diastolic = data_value.get("diastolic", "?")
                return f"{systolic}/{diastolic} mmHg"
            return str(data_value)

        if data_type in ("heart_rate", "resting_heart_rate"):
            return f"{data_value} bpm"

        if data_type in ("spo2", "oxygen_saturation"):
            return f"{data_value}%"

        if data_type in ("weight", "body_mass"):
            return f"{data_value} lbs"

        if data_type in ("temperature", "body_temperature"):
            return f"{data_value}°F"

        if data_type == "steps":
            return f"{data_value:,} steps"

        if data_type in ("blood_glucose", "glucose"):
            return f"{data_value} mg/dL"

        return str(data_value)
