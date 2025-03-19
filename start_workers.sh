#!/bin/bash
export PYTHONPATH=.
export REDIS_HOST=localhost
export REDIS_PORT=6379

# Ensure Redis is running
redis-server &
sleep 2

# Start Celery worker
celery -A app.core.celery_config.celery_app worker \
    --pool=solo \
    --loglevel=INFO \
    -E \
    --logfile=celery.log \
    -Q default \
    --max-tasks-per-child=100 \
    --time-limit=1800 \
    --soft-time-limit=1500