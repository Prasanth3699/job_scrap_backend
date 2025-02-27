# app/core/celery_config.py
from kombu import Queue, Exchange

# Broker settings
broker_url = "redis://localhost:6379/0"
result_backend = "redis://localhost:6379/1"

# Task settings
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "Asia/Kolkata"
enable_utc = True

# Worker settings
worker_prefetch_multiplier = 1
worker_max_tasks_per_child = 50
worker_max_memory_per_child = 150000
broker_connection_retry_on_startup = True  # Add this line

# Queue settings
task_default_queue = "default"
task_default_exchange = "default"
task_default_routing_key = "default"

# Define exchanges
default_exchange = Exchange("default", type="direct")
scraper_exchange = Exchange("scraper", type="direct")

# Define queues
task_queues = (
    Queue("default", default_exchange, routing_key="default"),
    Queue("scraper", scraper_exchange, routing_key="scraper"),
)

# Task routing
task_routes = {
    "app.tasks.scraper_tasks.*": {
        "queue": "scraper",
        "exchange": "scraper",
        "routing_key": "scraper",
    },
}
