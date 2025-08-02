"""
Message Handler Service - Routes incoming RabbitMQ messages to appropriate handlers
Integrates ML job service with the message broker system
"""

import asyncio
from typing import Dict, Any
from sqlalchemy.orm import Session

from ..core.logger import logger
from ..core.message_broker import EventType, EventMessage, get_message_broker
from ..db.session import get_db
from .ml_job_service import ml_job_service


class MessageHandler:
    """Handles incoming RabbitMQ messages and routes them to appropriate services"""

    def __init__(self):
        self.message_broker = get_message_broker("core-service")
        self.handlers = {
            EventType.JOB_DATA_REQUESTED: self._handle_job_data_request,
            EventType.BULK_JOB_DATA_REQUESTED: self._handle_bulk_job_data_request,
            # Add more handlers as needed
        }

    # async def start_consuming(self):
    #     """Start consuming messages from RabbitMQ"""
    #     logger.info("Starting message handler service...")

    #     await self.message_broker.subscribe_to_events(
    #         "core.ml_job_data_requested", self._handle_job_data_request, auto_ack=False
    #     )

    #     await self.message_broker.subscribe_to_events(
    #         "core.ml_bulk_job_data_requested",
    #         self._handle_bulk_job_data_request,
    #         auto_ack=False,
    #     )
    #     # Register message handlers
    #     for event_type, handler in self.handlers.items():
    #         await self.message_broker.subscribe_to_events(
    #             f"core.{event_type.value.replace('.', '_')}", handler, auto_ack=False
    #         )

    #     logger.info("Message handler service started successfully")

    async def start_consuming(self):
        logger.info("MessageHandler.start_consuming() called")

        try:
            logger.info("Subscribing to core.ml_job_data_requested...")
            await self.message_broker.subscribe_to_events(
                "core.ml_job_data_requested",
                self._handle_job_data_request,
                auto_ack=False,
            )
            logger.info("Successfully subscribed to core.ml_job_data_requested")

            logger.info("Subscribing to core.ml_bulk_job_data_requested...")
            await self.message_broker.subscribe_to_events(
                "core.ml_bulk_job_data_requested",
                self._handle_bulk_job_data_request,
                auto_ack=False,
            )
            logger.info("Successfully subscribed to core.ml_bulk_job_data_requested")

            # Start consuming messages in a background thread
            logger.info("Starting message consumption...")
            import threading
            consumption_thread = threading.Thread(target=self.message_broker.start_consuming, daemon=True)
            consumption_thread.start()
            logger.info("Message consumption started in background thread")

        except Exception as e:
            logger.error(f"Failed to subscribe to message queues: {e}")

    async def _handle_job_data_request(self, event_message: EventMessage):
        """Handle single job data request from ML service"""
        logger.info(f"Handling job data request: {event_message.event_id}")

        # Get database session
        db = next(get_db())
        try:
            await ml_job_service.handle_job_data_request(event_message, db)
        except Exception as e:
            logger.error(f"Error handling job data request: {str(e)}")
        finally:
            db.close()

    async def _handle_bulk_job_data_request(self, event_message: EventMessage):
        """Handle bulk job data request from ML service"""
        logger.info(f"Handling bulk job data request: {event_message.event_id}")

        # Get database session
        db = next(get_db())
        try:
            await ml_job_service.handle_bulk_job_data_request(event_message, db)
        except Exception as e:
            logger.error(f"Error handling bulk job data request: {str(e)}")
        finally:
            db.close()

    async def stop_consuming(self):
        """Stop consuming messages"""
        logger.info("Stopping message handler service...")
        # Add cleanup logic if needed
        logger.info("Message handler service stopped")


# Global message handler instance
message_handler = MessageHandler()
