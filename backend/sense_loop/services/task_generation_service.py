"""Task generation service - generates task instances from instruction plans."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from sense_loop.models import (
    Patient,
    PatientInstructionPlan,
    PatientInstructionTask,
)

logger = logging.getLogger(__name__)


@dataclass
class TaskGenerationConfig:
    """Configuration for task generation."""

    generation_window_days: int = 7
    default_time_window_minutes: int = 60
    default_time_of_day: str = "09:00"


class TaskGenerationService:
    """Service for generating task instances from instruction plans."""

    def __init__(self, db: Session, config: TaskGenerationConfig | None = None):
        self.db = db
        self.config = config or TaskGenerationConfig()

    def ensure_tasks_generated(
        self,
        plan: PatientInstructionPlan,
        through_date: date | None = None,
    ) -> int:
        """Ensure tasks exist through the specified date.

        Args:
            plan: The instruction plan
            through_date: Generate tasks through this date (default: today + window)

        Returns:
            Number of tasks created
        """
        if through_date is None:
            through_date = date.today() + timedelta(days=self.config.generation_window_days)

        # Get last generated date
        last_generated = plan.tasks_generated_through

        if last_generated and last_generated >= through_date:
            return 0  # Already generated through this date

        # Determine start date
        if last_generated is None:
            # First generation - start from effective_start or today
            start_date = max(plan.effective_start.date(), date.today())
        else:
            # Continue from last generated
            start_date = last_generated + timedelta(days=1)

        # Don't generate past effective_end
        if plan.effective_end and through_date > plan.effective_end.date():
            through_date = plan.effective_end.date()

        if start_date > through_date:
            return 0

        # Generate tasks
        tasks = self._generate_tasks_for_date_range(
            plan=plan,
            start_date=start_date,
            end_date=through_date,
        )

        # Add tasks to database
        for task in tasks:
            self.db.add(task)

        # Update tracking
        plan.tasks_generated_through = through_date
        self.db.flush()

        logger.info(
            "Generated %d tasks for plan %s from %s to %s",
            len(tasks),
            plan.id,
            start_date,
            through_date,
        )

        return len(tasks)

    def regenerate_on_plan_change(
        self, plan: PatientInstructionPlan
    ) -> tuple[int, int]:
        """Cancel pending future tasks and regenerate.

        Called when plan customizations change.

        Returns:
            Tuple of (cancelled_count, created_count)
        """
        today = date.today()

        # Cancel pending tasks from today onwards
        cancelled = 0
        for task in plan.tasks:
            if task.status == "pending" and task.scheduled_date >= today:
                task.status = "cancelled"
                task.updated_at = datetime.utcnow()
                cancelled += 1

        # Reset generation tracking
        plan.tasks_generated_through = today - timedelta(days=1)
        self.db.flush()

        # Regenerate tasks
        created = self.ensure_tasks_generated(plan)

        return cancelled, created

    def generate_daily_tasks(self) -> int:
        """Cron job: extend task window for all active plans.

        Should be called once per day (e.g., at 2 AM).

        Returns:
            Total number of tasks created
        """
        stmt = select(PatientInstructionPlan).where(
            PatientInstructionPlan.status == "active"
        )
        plans = list(self.db.execute(stmt).scalars().all())

        total_created = 0
        for plan in plans:
            try:
                created = self.ensure_tasks_generated(plan)
                total_created += created
            except Exception as e:
                logger.error("Error generating tasks for plan %s: %s", plan.id, e)

        logger.info("Daily task generation complete: %d tasks created", total_created)
        return total_created

    def _generate_tasks_for_date_range(
        self,
        plan: PatientInstructionPlan,
        start_date: date,
        end_date: date,
    ) -> list[PatientInstructionTask]:
        """Generate tasks for a date range based on plan content."""
        tasks = []

        # Get patient timezone
        patient = plan.patient
        timezone = patient.timezone if patient else "America/New_York"

        # Get reference date for relative timing
        reference_date = plan.reference_date

        # Process each section and item
        content = plan.resolved_content or {}
        for section in content.get("sections", []):
            section_id = section.get("id", "")

            for item in section.get("items", []):
                item_id = item.get("id", "")
                timing = item.get("timing")

                if not timing:
                    continue  # No timing means no recurring task

                # Generate task instances for this item
                item_tasks = self._generate_item_tasks(
                    plan=plan,
                    section_id=section_id,
                    item=item,
                    timing=timing,
                    start_date=start_date,
                    end_date=end_date,
                    reference_date=reference_date,
                    patient_timezone=timezone,
                )
                tasks.extend(item_tasks)

        return tasks

    def _generate_item_tasks(
        self,
        plan: PatientInstructionPlan,
        section_id: str,
        item: dict,
        timing: dict,
        start_date: date,
        end_date: date,
        reference_date: date | None,
        patient_timezone: str,
    ) -> list[PatientInstructionTask]:
        """Generate task instances for a single item."""
        tasks = []

        # Get task type information
        task_type = self._get_task_type(item)
        task_code = self._get_task_code(item)
        completion_method = self._get_completion_method(item)
        data_trigger_types = self._get_data_triggers(item)
        data_threshold = item.get("data_threshold") or (
            item.get("activity", {}).get("data_threshold")
        )
        confirmation_prompt = item.get("confirmation_prompt") or (
            item.get("activity", {}).get("confirmation_prompt")
        )

        # Calculate timing bounds
        timing_start, timing_end = self._calculate_timing_bounds(
            timing, reference_date, start_date, end_date
        )

        if timing_start > end_date or (timing_end and timing_end < start_date):
            return []  # Outside of timing bounds

        # Adjust start/end to timing bounds
        actual_start = max(start_date, timing_start)
        actual_end = min(end_date, timing_end) if timing_end else end_date

        # Get scheduled dates based on timing pattern
        scheduled_dates = self._expand_timing_to_dates(
            timing, actual_start, actual_end
        )

        # Get times of day
        times_of_day = timing.get("timeOfDay", [self.config.default_time_of_day])
        frequency = timing.get("frequency", 1)

        # If no specific times but frequency > 1, distribute throughout day
        if not times_of_day and frequency > 1:
            times_of_day = self._distribute_times(frequency)
        elif not times_of_day:
            times_of_day = [self.config.default_time_of_day]

        # Generate tasks for each date and time
        for scheduled_date in scheduled_dates:
            for time_str in times_of_day:
                # Calculate UTC datetime
                scheduled_at, local_time = self._calculate_scheduled_datetime(
                    scheduled_date, time_str, patient_timezone
                )

                task = PatientInstructionTask(
                    id=uuid4(),
                    plan_id=plan.id,
                    patient_id=plan.patient_id,
                    plan_item_id=item.get("id", ""),
                    section_id=section_id,
                    task_type=task_type,
                    task_code=task_code,
                    title=item.get("title", "Task"),
                    description=item.get("description"),
                    completion_method=completion_method,
                    data_trigger_types=data_trigger_types,
                    data_threshold=data_threshold,
                    confirmation_prompt=confirmation_prompt,
                    scheduled_date=scheduled_date,
                    scheduled_at=scheduled_at,
                    scheduled_time_local=local_time,
                    patient_timezone=patient_timezone,
                    time_window_minutes=timing.get(
                        "windowMinutes", self.config.default_time_window_minutes
                    ),
                    status="pending",
                )
                tasks.append(task)

        return tasks

    def _get_task_type(self, item: dict) -> str:
        """Determine task type from item."""
        # Check activity if it's a reference
        activity = item.get("activity", {})
        if activity.get("category_code"):
            category = activity["category_code"]
            # Map category to task type
            category_map = {
                "wound-care": "wound_care",
                "medications": "medication",
                "activity": "activity",
                "monitoring": "monitoring",
                "education": "education",
                "follow-up": "follow_up",
            }
            return category_map.get(category, "other")

        # Fallback to item type
        return item.get("task_type", "other")

    def _get_task_code(self, item: dict) -> str:
        """Determine task code from item."""
        # Use explicit task_code if set
        if item.get("task_code"):
            return item["task_code"]

        # Check activity
        activity = item.get("activity", {})
        if activity.get("name"):
            return activity["name"]

        # Fallback to item ID
        return item.get("id", "task")

    def _get_completion_method(self, item: dict) -> str:
        """Determine completion method from item."""
        # Check item override
        if item.get("completion_method"):
            return item["completion_method"]

        # Check activity
        activity = item.get("activity", {})
        if activity.get("completion_method"):
            return activity["completion_method"]

        return "manual"

    def _get_data_triggers(self, item: dict) -> list[str] | None:
        """Get data trigger types from item."""
        # Check item override
        if item.get("data_trigger_types"):
            return item["data_trigger_types"]

        # Check activity
        activity = item.get("activity", {})
        if activity.get("data_trigger_types"):
            return activity["data_trigger_types"]

        return None

    def _calculate_timing_bounds(
        self,
        timing: dict,
        reference_date: date | None,
        default_start: date,
        default_end: date,
    ) -> tuple[date, date | None]:
        """Calculate the start and end dates for timing bounds."""
        bounds_type = timing.get("boundsType", "ongoing")

        if bounds_type == "ongoing":
            # Use relative start if specified
            relative_start_days = timing.get("relativeStartDays", 0)
            if reference_date:
                start = reference_date + timedelta(days=relative_start_days)
            else:
                start = default_start
            return start, None

        elif bounds_type == "duration":
            duration_days = timing.get("boundsDurationDays", 14)
            relative_start_days = timing.get("relativeStartDays", 0)

            if reference_date:
                start = reference_date + timedelta(days=relative_start_days)
            else:
                start = default_start

            end = start + timedelta(days=duration_days - 1)
            return start, end

        elif bounds_type == "date_range":
            start_str = timing.get("boundsStartDate")
            end_str = timing.get("boundsEndDate")

            start = (
                datetime.fromisoformat(start_str).date()
                if start_str
                else default_start
            )
            end = (
                datetime.fromisoformat(end_str).date()
                if end_str
                else None
            )
            return start, end

        return default_start, None

    def _expand_timing_to_dates(
        self,
        timing: dict,
        start_date: date,
        end_date: date,
    ) -> list[date]:
        """Expand timing pattern to list of dates."""
        dates = []

        period = timing.get("period", 1)
        period_unit = timing.get("periodUnit", "d")
        days_of_week = timing.get("dayOfWeek", [])

        current = start_date

        while current <= end_date:
            include_date = True

            # Check day of week filter
            if days_of_week:
                day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
                current_day = day_names[current.weekday()]
                include_date = current_day in days_of_week

            if include_date:
                dates.append(current)

            # Advance to next date based on period
            if period_unit == "d":
                current += timedelta(days=period)
            elif period_unit == "wk":
                current += timedelta(weeks=period)
            elif period_unit == "mo":
                # Approximate month as 30 days
                current += timedelta(days=30 * period)
            else:
                current += timedelta(days=period)

        return dates

    def _distribute_times(self, frequency: int) -> list[str]:
        """Distribute N times evenly throughout waking hours (7 AM - 10 PM)."""
        start_hour = 7
        end_hour = 22
        span = end_hour - start_hour

        times = []
        for i in range(frequency):
            hour = start_hour + (span * i) // frequency
            times.append(f"{hour:02d}:00")

        return times

    def _calculate_scheduled_datetime(
        self,
        scheduled_date: date,
        time_str: str,
        patient_timezone: str,
    ) -> tuple[datetime, str]:
        """Calculate UTC datetime from local date/time.

        Returns:
            Tuple of (utc_datetime, local_time_string)
        """
        try:
            tz = ZoneInfo(patient_timezone)
        except Exception:
            logger.warning("Invalid timezone %s, using UTC", patient_timezone)
            tz = ZoneInfo("UTC")

        # Parse time
        try:
            local_time = datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            local_time = time(9, 0)  # Default to 9 AM
            time_str = "09:00"

        # Combine date and time in patient's timezone
        local_dt = datetime.combine(scheduled_date, local_time, tzinfo=tz)

        # Convert to UTC
        utc_dt = local_dt.astimezone(ZoneInfo("UTC"))

        return utc_dt, time_str
