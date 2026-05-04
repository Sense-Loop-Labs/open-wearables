#!/bin/bash
set -e -x

# SENSE-LOOP: Added --concurrency=1 to serialize Medplum requests and avoid 429 errors
uv run celery -A app.main:celery_app worker --loglevel=info --pool=threads --concurrency=1 -Q default,sdk_sync,garmin_sync,webhook_sync
