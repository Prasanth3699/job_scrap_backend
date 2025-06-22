from celery import Celery
from celery.signals import setup_logging
import logging
from .config import get_settings

settings = get_settings()

celery_app = Celery(
    "tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks"],
)

# Enhanced configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,  # 30 minutes
    task_soft_time_limit=1500,  # 25 minutes
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
    task_reject_on_worker_lost=True,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
)


# Custom logging setup
@setup_logging.connect
def configure_logging(sender=None, **kwargs):
    logging.basicConfig(
        format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
        level=logging.INFO,
        handlers=[logging.StreamHandler(), logging.FileHandler("celery.log")],
    )
