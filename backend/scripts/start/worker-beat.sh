#!/usr/bin/env bash
set -e

# Combined Worker + Beat script for cost-optimized deployments
# Runs both Celery worker and beat scheduler in the same container
# Use this for pre-pilot/low-traffic environments only

echo "Starting combined Celery Worker + Beat..."

# Start beat in background
celery -A app.main:celery_app beat \
  --loglevel=info &

BEAT_PID=$!
echo "Beat started with PID $BEAT_PID"

# Start worker in foreground (will be the main process)
# Using threads pool and low concurrency for memory-constrained pre-pilot deployment
celery -A app.main:celery_app worker \
  --loglevel=info \
  --pool=threads \
  --concurrency=2 \
  --queues=default,sdk_sync,garmin_sync,webhook_sync \
  --time-limit=3600 \
  --soft-time-limit=3300 &

WORKER_PID=$!
echo "Worker started with PID $WORKER_PID"

# Handle shutdown gracefully
cleanup() {
  echo "Shutting down..."
  kill $WORKER_PID 2>/dev/null || true
  kill $BEAT_PID 2>/dev/null || true
  wait
  exit 0
}

trap cleanup SIGTERM SIGINT

# Wait for either process to exit
wait -n $WORKER_PID $BEAT_PID

# If one exits, stop the other
cleanup
