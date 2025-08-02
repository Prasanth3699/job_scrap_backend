#!/bin/bash
export PYTHONPATH=.
export REDIS_HOST=localhost
export REDIS_PORT=6379

# Ensure Redis is running
redis-server &
sleep 2

# Start Celery worker with prefork pool for better performance
celery -A app.core.celery_config.celery_app worker \
    --pool=prefork \
    --concurrency=4 \
    --loglevel=INFO \
    -E \
    --logfile=logs/celery.log \
    -Q default,scraping,email \
    --max-tasks-per-child=1000 \
    --time-limit=3600 \
    --soft-time-limit=3300 \
    --without-gossip \
    --without-mingle \
    --without-heartbeat