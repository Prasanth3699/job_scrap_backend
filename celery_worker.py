# celery_worker.py
import os
from celery import Celery

# Set the default Django settings module
os.environ.setdefault("CELERY_CONFIG_MODULE", "app.core.celery_config")

# Create Celery app
celery_app = Celery("job_scraper")

# Load config
celery_app.config_from_object("app.core.celery_config")

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.tasks"])

if __name__ == "__main__":
    celery_app.start()
