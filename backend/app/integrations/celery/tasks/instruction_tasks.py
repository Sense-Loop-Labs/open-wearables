"""Celery tasks for Sense Loop instruction templates and tasks."""

from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Any
from uuid import UUID

from celery import shared_task

from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger(__name__)


@shared_task(
    name="sense_loop.generate_daily_tasks",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
    soft_time_limit=300,
    time_limit=360,
)
def generate_daily_tasks(self) -> dict:
    """Generate tasks for all active instruction plans.

    This task extends the rolling 7-day task window for all active plans.
    Should be run daily (e.g., at 2 AM UTC).

    Returns:
        Summary of tasks generated
    """
    if not settings.sense_loop_enabled:
        return {"skipped": True, "reason": "sense_loop_disabled"}

    db = SessionLocal()
    try:
        from sense_loop.services import TaskGenerationService

        service = TaskGenerationService(db)
        total_created = service.generate_daily_tasks()
        db.commit()

        logger.info("Daily task generation complete: %d tasks created", total_created)

        return {
            "success": True,
            "tasks_created": total_created,
            "generated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        db.rollback()
        logger.error("Failed to generate daily tasks: %s", str(e), exc_info=True)
        raise
    finally:
        db.close()


@shared_task(
    name="sense_loop.process_task_notifications",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
)
def process_task_notifications(self) -> dict:
    """Process pending task notifications.

    Sends reminders, overdue notifications, and confirmation requests.
    Should be run frequently (e.g., every 5 minutes).

    Returns:
        Summary of notifications sent
    """
    if not settings.sense_loop_enabled:
        return {"skipped": True, "reason": "sense_loop_disabled"}

    db = SessionLocal()
    try:
        from sense_loop.services import ConfigService, TaskNotificationService, NotificationService

        # Check if notifications are enabled (checked on each invocation)
        config_service = ConfigService(db)
        if not config_service.are_notifications_enabled():
            return {"skipped": True, "reason": "notifications_disabled"}

        notification_service = NotificationService(db)
        service = TaskNotificationService(db, notification_service=notification_service)

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            summary = loop.run_until_complete(service.process_pending_notifications())
        finally:
            loop.close()

        db.commit()

        logger.info(
            "Task notifications processed: %d reminders, %d overdue, %d confirmations",
            summary.get("reminders_sent", 0),
            summary.get("overdue_sent", 0),
            summary.get("confirmations_sent", 0),
        )

        return {
            "success": True,
            **summary,
            "processed_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        db.rollback()
        logger.error("Failed to process task notifications: %s", str(e), exc_info=True)
        raise
    finally:
        db.close()


@shared_task(
    name="sense_loop.mark_overdue_tasks",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
)
def mark_overdue_tasks(self) -> dict:
    """Mark tasks as missed after their time window expires.

    Should be run periodically (e.g., every 15 minutes).

    Returns:
        Summary of tasks marked as missed
    """
    if not settings.sense_loop_enabled:
        return {"skipped": True, "reason": "sense_loop_disabled"}

    db = SessionLocal()
    try:
        from sense_loop.services import TaskCompletionService

        service = TaskCompletionService(db)
        missed_count = service.mark_overdue_tasks()
        db.commit()

        if missed_count > 0:
            logger.info("Marked %d tasks as missed", missed_count)

        return {
            "success": True,
            "tasks_marked_missed": missed_count,
            "processed_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        db.rollback()
        logger.error("Failed to mark overdue tasks: %s", str(e), exc_info=True)
        raise
    finally:
        db.close()


@shared_task(
    name="sense_loop.send_daily_task_summaries",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def send_daily_task_summaries(self) -> dict:
    """Send daily task summary notifications to patients.

    Should be run once per day (e.g., at 8 AM in each timezone).

    Returns:
        Summary of notifications sent
    """
    if not settings.sense_loop_enabled:
        return {"skipped": True, "reason": "sense_loop_disabled"}

    db = SessionLocal()
    try:
        from sqlalchemy import select
        from sense_loop.models import Patient, PatientInstructionPlan
        from sense_loop.services import TaskCompletionService, TaskNotificationService

        # Find patients with active plans
        stmt = (
            select(Patient)
            .join(PatientInstructionPlan)
            .where(
                Patient.is_active == True,  # noqa: E712
                PatientInstructionPlan.status == "active",
            )
            .distinct()
        )
        patients = list(db.execute(stmt).scalars().all())

        task_service = TaskCompletionService(db)
        notification_service = TaskNotificationService(db)

        today = date.today()
        summaries_sent = 0

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            for patient in patients:
                tasks = task_service.get_patient_tasks_for_date(patient.id, today)
                pending_tasks = [t for t in tasks if t.status == "pending"]

                if pending_tasks:
                    loop.run_until_complete(
                        notification_service.send_daily_summary(
                            patient_id=patient.id,
                            tasks=pending_tasks,
                        )
                    )
                    summaries_sent += 1
        finally:
            loop.close()

        db.commit()

        logger.info("Sent %d daily task summaries", summaries_sent)

        return {
            "success": True,
            "summaries_sent": summaries_sent,
            "patients_checked": len(patients),
            "sent_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        db.rollback()
        logger.error("Failed to send daily summaries: %s", str(e), exc_info=True)
        raise
    finally:
        db.close()


@shared_task(
    name="sense_loop.process_data_for_tasks",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
)
def process_data_for_tasks(
    self,
    patient_id: str,
    data_type: str,
    data_id: str,
    data_value: Any,
    timestamp: str,
) -> dict:
    """Process incoming health data for task auto-completion.

    Called when new health data arrives to check if it completes any pending tasks.

    Args:
        patient_id: Patient UUID as string
        data_type: Type of data (blood_pressure, heart_rate, etc.)
        data_id: UUID of the data record
        data_value: The data value (may be dict for BP, number for others)
        timestamp: ISO format timestamp

    Returns:
        Summary of tasks completed
    """
    if not settings.sense_loop_enabled:
        return {"skipped": True, "reason": "sense_loop_disabled"}

    db = SessionLocal()
    try:
        from sense_loop.services import TaskCompletionService, TaskNotificationService

        task_service = TaskCompletionService(db)
        notification_service = TaskNotificationService(db)

        # Parse timestamp
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        # Link notification service for success notifications
        task_service.notification_service = notification_service

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            completed_tasks = loop.run_until_complete(
                task_service.on_data_received(
                    patient_id=UUID(patient_id),
                    data_type=data_type,
                    data_id=UUID(data_id),
                    data_value=data_value,
                    timestamp=ts,
                )
            )
        finally:
            loop.close()

        db.commit()

        if completed_tasks:
            logger.info(
                "Auto-completed %d tasks from %s data for patient %s",
                len(completed_tasks),
                data_type,
                patient_id,
            )

        return {
            "success": True,
            "tasks_completed": len(completed_tasks),
            "task_ids": [str(t.id) for t in completed_tasks],
        }

    except Exception as e:
        db.rollback()
        logger.error(
            "Failed to process data for tasks: %s", str(e), exc_info=True
        )
        raise
    finally:
        db.close()


@shared_task(
    name="sense_loop.process_questionnaire_for_tasks",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
)
def process_questionnaire_for_tasks(
    self,
    patient_id: str,
    questionnaire_code: str,
    response_id: str,
    submitted_at: str,
) -> dict:
    """Process questionnaire submission for task auto-completion.

    Called when a questionnaire is submitted to check if it completes any pending tasks.

    Args:
        patient_id: Patient UUID as string
        questionnaire_code: Code of the questionnaire
        response_id: UUID of the response record
        submitted_at: ISO format timestamp

    Returns:
        Summary of tasks completed
    """
    if not settings.sense_loop_enabled:
        return {"skipped": True, "reason": "sense_loop_disabled"}

    db = SessionLocal()
    try:
        from sense_loop.services import TaskCompletionService

        service = TaskCompletionService(db)

        ts = datetime.fromisoformat(submitted_at.replace("Z", "+00:00"))

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            completed_tasks = loop.run_until_complete(
                service.on_questionnaire_submitted(
                    patient_id=UUID(patient_id),
                    questionnaire_code=questionnaire_code,
                    response_id=UUID(response_id),
                    submitted_at=ts,
                )
            )
        finally:
            loop.close()

        db.commit()

        if completed_tasks:
            logger.info(
                "Completed %d tasks from questionnaire %s for patient %s",
                len(completed_tasks),
                questionnaire_code,
                patient_id,
            )

        return {
            "success": True,
            "tasks_completed": len(completed_tasks),
            "task_ids": [str(t.id) for t in completed_tasks],
        }

    except Exception as e:
        db.rollback()
        logger.error(
            "Failed to process questionnaire for tasks: %s", str(e), exc_info=True
        )
        raise
    finally:
        db.close()
