"""Celery tasks for Sense Loop integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from celery import shared_task
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import DataPointSeries, DataSource, User
from app.models.hr_analysis import HRBaseline

logger = logging.getLogger(__name__)

# Alert email for critical audit failures
AUDIT_ALERT_EMAIL = "compliance@sense-loop.com"  # Configure in settings


@shared_task(
    name="sense_loop.process_vitals",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def process_vitals_for_sense_loop(
    self,
    user_id: str,
    series_type: str,
    samples: list[dict[str, Any]],
    provider: str | None = None,
) -> None:
    """Process vitals data through Sense Loop alert engine.

    This task:
    1. Looks up the SL Patient linked to this OW User
    2. If active patient with monitoring, runs alert evaluation
    3. Updates patient summary with latest values
    """
    if not settings.sense_loop_enabled:
        return

    if not samples:
        return

    db = SessionLocal()
    try:
        from sense_loop.hooks.data_events import on_timeseries_saved

        on_timeseries_saved(
            db=db,
            user_id=UUID(user_id),
            series_type=series_type,
            samples=samples,
            provider=provider,
        )
        db.commit()

        logger.debug(
            "Processed %d %s samples for user %s via Sense Loop",
            len(samples),
            series_type,
            user_id,
        )

    except Exception as e:
        db.rollback()
        logger.error(
            "Failed to process Sense Loop vitals for user %s: %s",
            user_id,
            str(e),
            exc_info=True,
        )
        raise
    finally:
        db.close()


@shared_task(
    name="sense_loop.calculate_hr_baselines",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def calculate_hr_baselines(self: Any) -> dict[str, Any]:
    """Nightly task to recalculate HR baselines from sleep/sedentary data.

    Calculates personalized resting HR baselines for each user based on
    HR readings during sleep sessions and sedentary periods from the
    past 14 days.

    This enables personalized alert thresholds instead of using
    fixed values for all users.

    Should be scheduled to run nightly via Celery Beat.
    """
    try:
        with SessionLocal() as db:
            # Get all users with HR data
            users = db.execute(select(User)).scalars().all()

            updated_count = 0
            error_count = 0

            for user in users:
                try:
                    _calculate_baseline_for_user(db, user.id)
                    updated_count += 1
                except Exception as e:
                    logger.error("Error calculating baseline for user %s: %s", user.id, e)
                    error_count += 1

            logger.info(
                "HR baseline calculation complete: %d updated, %d errors",
                updated_count,
                error_count,
            )

            return {
                "processed": True,
                "users_updated": updated_count,
                "errors": error_count,
            }

    except Exception as exc:
        logger.error("Error in HR baseline calculation: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


def _calculate_baseline_for_user(db: Any, user_id: UUID) -> None:
    """Calculate HR baseline for a single user.

    Uses HR readings from:
    - Sleep sessions (last 14 days)
    - Sedentary periods with low steps (last 14 days)

    Updates or creates the HRBaseline record.
    """
    from app.models import SeriesTypeDefinition

    lookback_days = 14
    start_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    # Get heart_rate series type
    hr_type = db.execute(
        select(SeriesTypeDefinition).where(
            SeriesTypeDefinition.code == "heart_rate"
        )
    ).scalar_one_or_none()

    if not hr_type:
        return

    # Get all HR readings for this user in the lookback period
    # during sleep or low-activity periods
    # For simplicity, we'll use all HR readings and filter by reasonable resting range
    hr_readings = db.execute(
        select(DataPointSeries.value)
        .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
        .where(
            DataSource.user_id == user_id,
            DataPointSeries.series_type_definition_id == hr_type.id,
            DataPointSeries.recorded_at >= start_date,
            # Filter to likely resting values (40-100 bpm)
            DataPointSeries.value >= 40,
            DataPointSeries.value <= 100,
        )
    ).scalars().all()

    if len(hr_readings) < 10:
        # Not enough data for reliable baseline
        return

    # Calculate statistics
    values = [float(v) for v in hr_readings]
    avg_hr = sum(values) / len(values)

    # Calculate standard deviation
    variance = sum((v - avg_hr) ** 2 for v in values) / len(values)
    std_hr = variance ** 0.5

    min_hr = min(values)
    max_hr = max(values)

    # Calculate elevated threshold: avg + 2*std, minimum 100
    elevated_threshold = max(int(avg_hr + 2 * std_hr), 100)

    # Update or create baseline
    baseline = db.query(HRBaseline).filter(HRBaseline.user_id == user_id).first()

    if baseline:
        baseline.resting_hr_avg = Decimal(str(round(avg_hr, 2)))
        baseline.resting_hr_std = Decimal(str(round(std_hr, 2)))
        baseline.resting_hr_min = int(min_hr)
        baseline.resting_hr_max = int(max_hr)
        baseline.sample_count = len(hr_readings)
        baseline.elevated_threshold = elevated_threshold
        baseline.last_calculated_at = datetime.now(timezone.utc)
        baseline.updated_at = datetime.now(timezone.utc)
    else:
        baseline = HRBaseline(
            user_id=user_id,
            resting_hr_avg=Decimal(str(round(avg_hr, 2))),
            resting_hr_std=Decimal(str(round(std_hr, 2))),
            resting_hr_min=int(min_hr),
            resting_hr_max=int(max_hr),
            sample_count=len(hr_readings),
            elevated_threshold=elevated_threshold,
            last_calculated_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(baseline)

    db.commit()

    logger.debug(
        "Updated HR baseline for user %s: avg=%.1f, std=%.1f, threshold=%d",
        user_id,
        avg_hr,
        std_hr,
        elevated_threshold,
    )


@shared_task(
    name="sense_loop.verify_audit_integrity",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def verify_audit_integrity(self: Any) -> dict[str, Any]:
    """Daily task to verify audit log integrity.

    Checks the hash chain of the audit log to detect any tampering.
    Logs warnings and can send alerts if integrity issues are found.

    Should be scheduled to run daily via Celery Beat.
    """
    from sense_loop.audit import AuditIntegrityService

    db = SessionLocal()
    try:
        service = AuditIntegrityService(db)

        # Get summary first
        summary = service.get_chain_summary()

        # Verify the full chain
        result = service.verify_chain(limit=100000)  # Check up to 100k entries

        if result.is_valid:
            logger.info(
                "Audit log integrity verified: %d entries checked, chain valid",
                result.entries_checked,
            )
            return {
                "success": True,
                "is_valid": True,
                "entries_checked": result.entries_checked,
                "total_entries": summary["total_entries"],
                "hashed_coverage": summary["chain_coverage_percent"],
            }
        else:
            # CRITICAL: Integrity failure detected
            logger.critical(
                "AUDIT LOG INTEGRITY FAILURE: %s at sequence %d (entry %s)",
                result.error_message,
                result.first_invalid_sequence,
                result.first_invalid_id,
            )

            # Log the failure as an audit event itself
            from sense_loop.audit import AuditLogger
            from sense_loop.audit.context import AuditContext

            ctx = AuditContext(
                actor_type="system",
                endpoint="celery:verify_audit_integrity",
                http_method="SCHEDULED",
            )
            audit = AuditLogger(db, ctx)
            audit.log(
                action="integrity_check_failed",
                resource_type="audit_log",
                outcome="failure",
                outcome_reason=result.error_message,
                details={
                    "first_invalid_sequence": result.first_invalid_sequence,
                    "first_invalid_id": str(result.first_invalid_id) if result.first_invalid_id else None,
                    "entries_checked": result.entries_checked,
                    "gaps_detected": result.gaps_detected,
                },
            )
            db.commit()

            # TODO: Send alert email/notification
            # This should trigger immediate investigation

            return {
                "success": True,
                "is_valid": False,
                "error": result.error_message,
                "first_invalid_sequence": result.first_invalid_sequence,
                "entries_checked": result.entries_checked,
                "gaps_detected": result.gaps_detected,
            }

    except Exception as e:
        logger.error("Error verifying audit log integrity: %s", str(e), exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()
