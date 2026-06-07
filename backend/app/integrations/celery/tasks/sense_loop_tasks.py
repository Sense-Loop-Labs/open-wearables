"""Celery tasks for Sense Loop integration."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from celery import shared_task

from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger(__name__)


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
