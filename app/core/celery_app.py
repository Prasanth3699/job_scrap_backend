from celery import Celery

celery_app = Celery("job_scraper")


# This will be configured later
def configure_celery():
    celery_app.config_from_object("app.core.celery_config")
    return celery_app
