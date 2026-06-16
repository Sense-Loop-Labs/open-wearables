"""Health check endpoints for Sense Loop infrastructure."""

from datetime import datetime, timezone
from typing import Any

from celery import current_app as celery_app
from fastapi import APIRouter
from pydantic import BaseModel
from redis import Redis

from app.config import settings


router = APIRouter()


class CeleryWorkerStatus(BaseModel):
    """Status of a Celery worker."""

    name: str
    status: str  # "online", "offline"
    queues: list[str] = []


class QueueStatus(BaseModel):
    """Status of a Celery queue."""

    name: str
    length: int
    status: str  # "ok", "warning", "critical"


class CeleryHealthResponse(BaseModel):
    """Response from Celery health check."""

    status: str  # "healthy", "degraded", "unhealthy"
    workers: list[CeleryWorkerStatus]
    queues: list[QueueStatus]
    message: str | None = None
    checked_at: datetime


# Queue length thresholds
QUEUE_WARNING_THRESHOLD = 100
QUEUE_CRITICAL_THRESHOLD = 500


def get_redis_client() -> Redis:
    """Get a Redis client for checking queue lengths."""
    return Redis.from_url(settings.redis_url)


def check_celery_workers() -> list[CeleryWorkerStatus]:
    """Check if Celery workers are responsive."""
    workers = []

    try:
        # Use inspect to ping workers
        inspect = celery_app.control.inspect(timeout=5.0)
        ping_response = inspect.ping()

        if ping_response:
            # Get active queues for each worker
            active_queues = inspect.active_queues() or {}

            for worker_name, response in ping_response.items():
                if response.get("ok") == "pong":
                    # Get queue names for this worker
                    worker_queues = active_queues.get(worker_name, [])
                    queue_names = [q.get("name", "unknown") for q in worker_queues]

                    workers.append(
                        CeleryWorkerStatus(
                            name=worker_name,
                            status="online",
                            queues=queue_names,
                        )
                    )
                else:
                    workers.append(
                        CeleryWorkerStatus(
                            name=worker_name,
                            status="offline",
                        )
                    )
        else:
            # No workers responded
            pass

    except Exception as e:
        # If we can't connect at all, return empty list
        # The overall status will be unhealthy
        pass

    return workers


def check_queue_lengths() -> list[QueueStatus]:
    """Check the length of Celery queues."""
    queues = []
    queue_names = ["default", "sdk_sync", "garmin_sync", "webhook_sync"]

    try:
        redis_client = get_redis_client()

        for queue_name in queue_names:
            # Celery stores queues as Redis lists
            length = redis_client.llen(queue_name)

            if length >= QUEUE_CRITICAL_THRESHOLD:
                status = "critical"
            elif length >= QUEUE_WARNING_THRESHOLD:
                status = "warning"
            else:
                status = "ok"

            queues.append(
                QueueStatus(
                    name=queue_name,
                    length=length,
                    status=status,
                )
            )

        redis_client.close()

    except Exception as e:
        # If we can't check queues, report as unknown
        for queue_name in queue_names:
            queues.append(
                QueueStatus(
                    name=queue_name,
                    length=-1,
                    status="unknown",
                )
            )

    return queues


@router.get("/celery", response_model=CeleryHealthResponse)
def celery_health() -> CeleryHealthResponse:
    """Check health of Celery workers and queues.

    Returns:
        - healthy: All workers online, no queue backlog
        - degraded: Some workers offline OR queue warning threshold exceeded
        - unhealthy: No workers online OR queue critical threshold exceeded

    Use this endpoint for monitoring/alerting. Returns 200 even when unhealthy
    to allow monitoring tools to parse the response body.
    """
    workers = check_celery_workers()
    queues = check_queue_lengths()

    # Determine overall status
    online_workers = [w for w in workers if w.status == "online"]
    critical_queues = [q for q in queues if q.status == "critical"]
    warning_queues = [q for q in queues if q.status == "warning"]

    if not online_workers:
        status = "unhealthy"
        message = "No Celery workers are responding"
    elif critical_queues:
        status = "unhealthy"
        queue_names = ", ".join(q.name for q in critical_queues)
        message = f"Queue backlog critical: {queue_names}"
    elif warning_queues:
        status = "degraded"
        queue_names = ", ".join(q.name for q in warning_queues)
        message = f"Queue backlog warning: {queue_names}"
    elif len(online_workers) < len(workers):
        status = "degraded"
        offline = [w.name for w in workers if w.status == "offline"]
        message = f"Some workers offline: {', '.join(offline)}"
    else:
        status = "healthy"
        message = f"{len(online_workers)} worker(s) online, all queues clear"

    return CeleryHealthResponse(
        status=status,
        workers=workers,
        queues=queues,
        message=message,
        checked_at=datetime.now(timezone.utc),
    )


@router.get("/celery/simple")
def celery_health_simple() -> dict[str, Any]:
    """Simple health check that returns just status.

    Returns 200 with {"status": "healthy"} if all is well.
    Returns 200 with {"status": "unhealthy", "message": "..."} if not.

    Use this for simple uptime monitoring that just needs pass/fail.
    """
    response = celery_health()
    return {
        "status": response.status,
        "message": response.message,
        "workers_online": len([w for w in response.workers if w.status == "online"]),
    }
