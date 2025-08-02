"""
RabbitMQ message broker implementation for event-driven architecture.
Handles inter-service communication, job processing, and event distribution.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, asdict
from enum import Enum
import pika
from pika.adapters.asyncio_connection import AsyncioConnection
from pika.exchange_type import ExchangeType
import os
from contextlib import asynccontextmanager

from ..core.logger import logger
from ..core.config import get_settings

settings = get_settings()


class EventType(Enum):
    """Event types for the system"""

    # Job events
    JOB_SCRAPED = "job.scraped"
    JOB_UPDATED = "job.updated"
    JOB_DELETED = "job.deleted"
    JOBS_BULK_IMPORTED = "jobs.bulk_imported"

    # User events
    USER_REGISTERED = "user.registered"
    USER_LOGIN = "user.login"
    USER_PROFILE_UPDATED = "user.profile_updated"

    # ML events
    JOB_ANALYSIS_REQUESTED = "ml.job_analysis_requested"
    JOB_ANALYSIS_COMPLETED = "ml.job_analysis_completed"
    RECOMMENDATION_GENERATED = "ml.recommendation_generated"
    JOB_DATA_REQUESTED = "ml.job_data_requested"
    JOB_DATA_RESPONSE = "ml.job_data_response"
    BULK_JOB_DATA_REQUESTED = "ml.bulk_job_data_requested"
    BULK_JOB_DATA_RESPONSE = "ml.bulk_job_data_response"

    # LLM events
    LLM_PROCESSING_REQUESTED = "llm.processing_requested"
    LLM_PROCESSING_COMPLETED = "llm.processing_completed"

    # System events
    CLEANUP_REQUESTED = "system.cleanup_requested"
    HEALTH_CHECK_FAILED = "system.health_check_failed"

    # Notification events
    EMAIL_REQUEST = "notification.email_request"
    ALERT_TRIGGERED = "notification.alert_triggered"


@dataclass
class EventMessage:
    """Standard event message structure"""

    event_id: str
    event_type: EventType
    source_service: str
    timestamp: str
    data: Dict[str, Any]
    correlation_id: Optional[str] = None
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventMessage":
        """Create from dictionary"""
        data["event_type"] = EventType(data["event_type"])
        return cls(**data)


class RabbitMQConfig:
    """RabbitMQ configuration"""

    def __init__(self):
        self.connection_url = os.getenv("RABBITMQ_URL")
        self.exchange_name = "job_scraper_events"
        self.dead_letter_exchange = "job_scraper_dlx"
        self.retry_exchange = "job_scraper_retry"

        # Queue configurations
        self.queues = {
            # Core service queues
            "core.jobs": {
                "routing_keys": ["job.*", "system.*"],
                "durable": True,
                "auto_delete": False,
            },
            "core.users": {
                "routing_keys": ["user.*"],
                "durable": True,
                "auto_delete": False,
            },
            # ML service queues
            "ml.analysis": {
                "routing_keys": ["ml.*", "job.scraped", "job.updated"],
                "durable": True,
                "auto_delete": False,
            },
            "core.ml_job_data_requested": {
                "routing_keys": ["ml.job_data_requested"],
                "durable": True,
                "auto_delete": False,
            },
            "core.ml_bulk_job_data_requested": {
                "routing_keys": ["ml.bulk_job_data_requested"],
                "durable": True,
                "auto_delete": False,
            },
            # LLM service queues
            "llm.processing": {
                "routing_keys": ["llm.*", "user.profile_updated"],
                "durable": True,
                "auto_delete": False,
            },
            # Notification queues
            "notifications.email": {
                "routing_keys": ["notification.*"],
                "durable": True,
                "auto_delete": False,
            },
            # System maintenance
            "system.cleanup": {
                "routing_keys": ["system.cleanup_requested"],
                "durable": True,
                "auto_delete": False,
            },
        }


class MessageBroker:
    """RabbitMQ message broker for event-driven communication"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.config = RabbitMQConfig()
        self.connection = None
        self.channel = None
        self.consumers = {}
        self.is_connected = False

    async def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            logger.info(f"Connecting to RabbitMQ: {self.config.connection_url}")

            # Parse connection URL
            parameters = pika.URLParameters(self.config.connection_url)
            parameters.heartbeat = 600
            parameters.blocked_connection_timeout = 300

            # Create connection
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            # Setup exchanges and queues
            await self._setup_infrastructure()

            self.is_connected = True
            logger.info("Successfully connected to RabbitMQ")

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            raise

    async def _setup_infrastructure(self):
        """Setup RabbitMQ exchanges, queues, and bindings"""
        try:
            # Main exchange for events
            self.channel.exchange_declare(
                exchange=self.config.exchange_name,
                exchange_type=ExchangeType.topic,
                durable=True,
            )

            # Dead letter exchange
            self.channel.exchange_declare(
                exchange=self.config.dead_letter_exchange,
                exchange_type=ExchangeType.direct,
                durable=True,
            )

            # Retry exchange
            self.channel.exchange_declare(
                exchange=self.config.retry_exchange,
                exchange_type=ExchangeType.direct,
                durable=True,
            )

            # Setup queues
            for queue_name, queue_config in self.config.queues.items():
                # Main queue
                self.channel.queue_declare(
                    queue=queue_name,
                    durable=queue_config["durable"],
                    auto_delete=queue_config["auto_delete"],
                    arguments={
                        "x-dead-letter-exchange": self.config.dead_letter_exchange,
                        "x-dead-letter-routing-key": f"{queue_name}.dlq",
                        "x-message-ttl": 3600000,  # 1 hour TTL
                    },
                )

                # Bind to routing keys
                for routing_key in queue_config["routing_keys"]:
                    self.channel.queue_bind(
                        exchange=self.config.exchange_name,
                        queue=queue_name,
                        routing_key=routing_key,
                    )

                # Dead letter queue
                dlq_name = f"{queue_name}.dlq"
                self.channel.queue_declare(
                    queue=dlq_name, durable=True, auto_delete=False
                )
                self.channel.queue_bind(
                    exchange=self.config.dead_letter_exchange,
                    queue=dlq_name,
                    routing_key=f"{queue_name}.dlq",
                )

                # Retry queue
                retry_queue_name = f"{queue_name}.retry"
                self.channel.queue_declare(
                    queue=retry_queue_name,
                    durable=True,
                    auto_delete=False,
                    arguments={
                        "x-message-ttl": 30000,  # 30 seconds delay
                        "x-dead-letter-exchange": self.config.exchange_name,
                        "x-dead-letter-routing-key": routing_key,
                    },
                )
                self.channel.queue_bind(
                    exchange=self.config.retry_exchange,
                    queue=retry_queue_name,
                    routing_key=f"{queue_name}.retry",
                )

            logger.info("RabbitMQ infrastructure setup completed")

        except Exception as e:
            logger.error(f"Failed to setup RabbitMQ infrastructure: {str(e)}")
            raise

    async def publish_event(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> str:
        """Publish an event to the message broker"""

        if not self.is_connected:
            await self.connect()

        try:
            # Create event message
            event_id = str(uuid.uuid4())
            event = EventMessage(
                event_id=event_id,
                event_type=event_type,
                source_service=self.service_name,
                timestamp=datetime.now(timezone.utc).isoformat(),
                data=data,
                correlation_id=correlation_id or event_id,
            )

            # Publish to exchange
            self.channel.basic_publish(
                exchange=self.config.exchange_name,
                routing_key=event_type.value,
                body=json.dumps(event.to_dict()),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Persistent message
                    message_id=event_id,
                    correlation_id=correlation_id,
                    timestamp=int(datetime.now(timezone.utc).timestamp()),
                    headers={
                        "source_service": self.service_name,
                        "event_type": event_type.value,
                    },
                ),
            )

            logger.info(f"Published event {event_type.value} with ID {event_id}")
            return event_id

        except Exception as e:
            logger.error(f"Failed to publish event {event_type.value}: {str(e)}")
            raise

    async def subscribe_to_events(
        self,
        queue_name: str,
        handler: Callable[[EventMessage], None],
        auto_ack: bool = False,
    ):
        """Subscribe to events from a specific queue"""

        if not self.is_connected:
            await self.connect()

        try:

            def callback(ch, method, properties, body):
                """Message callback handler"""
                try:
                    # Parse message
                    message_data = json.loads(body)
                    event = EventMessage.from_dict(message_data)

                    logger.info(
                        f"Received event {event.event_type.value} from queue {queue_name}"
                    )

                    # Call handler - handle async properly
                    import concurrent.futures
                    import asyncio

                    if asyncio.iscoroutinefunction(handler):
                        # For async handlers, we need to schedule them properly
                        def run_async_handler():
                            # Create new event loop for this thread
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                loop.run_until_complete(handler(event))
                            finally:
                                loop.close()

                        # Run in thread pool to avoid blocking
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(run_async_handler)
                            # Wait for completion
                            future.result()
                    else:
                        handler(event)

                    # Acknowledge message if not auto-ack
                    if not auto_ack:
                        ch.basic_ack(delivery_tag=method.delivery_tag)

                except Exception as e:
                    logger.error(
                        f"Error processing message from {queue_name}: {str(e)}"
                    )

                    # Check retry count
                    try:
                        message_data = json.loads(body)
                        event = EventMessage.from_dict(message_data)
                        retry_count = event.retry_count
                    except:
                        retry_count = 0

                    if retry_count < 3:  # Max 3 retries
                        # Send to retry queue
                        self._send_to_retry_queue(queue_name, body, retry_count + 1)
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                    else:
                        # Send to dead letter queue
                        logger.error(
                            f"Max retries exceeded for message, sending to DLQ"
                        )
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            # Setup consumer
            self.channel.basic_qos(prefetch_count=10)  # Process 10 messages at a time
            self.channel.basic_consume(
                queue=queue_name, on_message_callback=callback, auto_ack=auto_ack
            )

            self.consumers[queue_name] = callback
            logger.info(f"Subscribed to queue {queue_name}")

        except Exception as e:
            logger.error(f"Failed to subscribe to queue {queue_name}: {str(e)}")
            raise

    def _send_to_retry_queue(
        self, original_queue: str, message_body: bytes, retry_count: int
    ):
        """Send message to retry queue"""
        try:
            # Update retry count in message
            message_data = json.loads(message_body)
            message_data["retry_count"] = retry_count

            retry_queue_name = f"{original_queue}.retry"

            self.channel.basic_publish(
                exchange=self.config.retry_exchange,
                routing_key=f"{original_queue}.retry",
                body=json.dumps(message_data),
                properties=pika.BasicProperties(
                    delivery_mode=2, headers={"retry_count": retry_count}
                ),
            )

            logger.info(
                f"Sent message to retry queue {retry_queue_name} (attempt {retry_count})"
            )

        except Exception as e:
            logger.error(f"Failed to send message to retry queue: {str(e)}")

    async def publish_message(self, event_message: EventMessage, routing_key: str):
        """Publish a pre-built event message"""
        if not self.is_connected:
            await self.connect()

        try:
            self.channel.basic_publish(
                exchange=self.config.exchange_name,
                routing_key=routing_key,
                body=json.dumps(event_message.to_dict()),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    message_id=event_message.event_id,
                    correlation_id=event_message.correlation_id,
                    timestamp=int(datetime.now(timezone.utc).timestamp()),
                    headers={
                        "source_service": event_message.source_service,
                        "event_type": event_message.event_type.value,
                    },
                ),
            )
            logger.info(f"Published message {event_message.event_type.value}")
        except Exception as e:
            logger.error(f"Failed to publish message: {str(e)}")
            raise

    def start_consuming(self):
        """Start consuming messages (blocking operation)"""
        if not self.is_connected:
            raise RuntimeError("Not connected to RabbitMQ")

        try:
            logger.info("Starting message consumption...")
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Stopping message consumption...")
            self.channel.stop_consuming()
            self.connection.close()

    async def close(self):
        """Close connection to RabbitMQ"""
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()

            if self.connection and not self.connection.is_closed:
                self.connection.close()

            self.is_connected = False
            logger.info("Disconnected from RabbitMQ")

        except Exception as e:
            logger.error(f"Error closing RabbitMQ connection: {str(e)}")

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics for monitoring"""
        if not self.is_connected:
            return {"error": "Not connected to RabbitMQ"}

        try:
            stats = {}

            for queue_name in self.config.queues.keys():
                try:
                    method = self.channel.queue_declare(queue=queue_name, passive=True)
                    stats[queue_name] = {
                        "message_count": method.method.message_count,
                        "consumer_count": method.method.consumer_count,
                    }
                except Exception as e:
                    stats[queue_name] = {"error": str(e)}

            return stats

        except Exception as e:
            logger.error(f"Error getting queue stats: {str(e)}")
            return {"error": str(e)}


# Global message broker instance
message_broker = None


def get_message_broker(service_name: str = "core-service") -> MessageBroker:
    """Get global message broker instance"""
    global message_broker

    if message_broker is None:
        message_broker = MessageBroker(service_name)

    return message_broker


# Context manager for handling connections
@asynccontextmanager
async def message_broker_context(service_name: str = "core-service"):
    """Context manager for message broker"""
    broker = get_message_broker(service_name)

    try:
        await broker.connect()
        yield broker
    finally:
        await broker.close()


# Event handlers for common events
class EventHandlers:
    """Common event handlers for the core service"""

    @staticmethod
    def handle_job_scraped(event: EventMessage):
        """Handle job scraped event"""
        try:
            job_data = event.data
            logger.info(
                f"Processing scraped job: {job_data.get('job_title', 'Unknown')}"
            )

            # Here you could trigger ML analysis, notifications, etc.
            # For now, just log

        except Exception as e:
            logger.error(f"Error handling job scraped event: {str(e)}")
            raise

    @staticmethod
    def handle_user_registered(event: EventMessage):
        """Handle user registration event"""
        try:
            user_data = event.data
            logger.info(
                f"Processing user registration: {user_data.get('email', 'Unknown')}"
            )

            # Could trigger welcome email, setup default preferences, etc.

        except Exception as e:
            logger.error(f"Error handling user registration event: {str(e)}")
            raise

    @staticmethod
    def handle_cleanup_requested(event: EventMessage):
        """Handle system cleanup request"""
        try:
            cleanup_type = event.data.get("cleanup_type", "full")
            logger.info(f"Processing cleanup request: {cleanup_type}")

            # Trigger data retention cleanup
            from ..services.data_retention_service import schedule_cleanup_jobs

            schedule_cleanup_jobs()

        except Exception as e:
            logger.error(f"Error handling cleanup request: {str(e)}")
            raise


# Startup function to initialize message broker
async def initialize_message_broker(service_name: str = "core-service"):
    """Initialize message broker on application startup"""
    try:
        broker = get_message_broker(service_name)
        await broker.connect()

        # Subscribe to relevant queues for core service
        if service_name == "core-service":
            await broker.subscribe_to_events(
                "core.jobs", EventHandlers.handle_job_scraped
            )
            await broker.subscribe_to_events(
                "core.users", EventHandlers.handle_user_registered
            )
            await broker.subscribe_to_events(
                "system.cleanup", EventHandlers.handle_cleanup_requested
            )

        logger.info(f"Message broker initialized for {service_name}")
        return broker

    except Exception as e:
        logger.error(f"Failed to initialize message broker: {str(e)}")
        raise


# Cleanup function for application shutdown
async def cleanup_message_broker():
    """Cleanup message broker on application shutdown"""
    global message_broker

    if message_broker:
        await message_broker.close()
        message_broker = None
        logger.info("Message broker cleanup completed")
