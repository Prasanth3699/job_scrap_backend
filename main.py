"""
Main FastAPI application module.
Handles application lifecycle, middleware setup, and service initialization.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

from app.services.settings_service import SettingsService
from app.services.scheduler_service import init_scheduler, scheduler
from app.api.router import api_router
from app.db.session import get_db
from app.core.logger import logger
from app.core.message_broker import initialize_message_broker, cleanup_message_broker
from app.services.message_handler import message_handler
from app.middleware.advanced_rate_limit import RateLimitMiddleware
from app.middleware.monitoring_middleware import (
    MonitoringMiddleware,
    PerformanceMiddleware,
    CorrelationMiddleware,
)

# Load environment variables
load_dotenv()

# CORS origins configuration
CORS_ORIGINS = [
    "http://localhost",
    "http://localhost:80",
    "http://localhost:3000",
]

# Rate-limited endpoints
PROTECTED_ENDPOINTS = [
    "/api/profile/upload-resume",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler for startup and shutdown events.
    Manages service initialization and cleanup in proper order.
    """
    # Startup sequence
    logger.info("Starting application initialization...")

    startup_success = False
    broker_initialized = False
    scheduler_initialized = False
    message_handler_started = False

    try:
        # Initialize scheduler
        init_scheduler()
        scheduler_initialized = True
        logger.info("Scheduler initialized successfully")

        # Initialize message broker for event-driven architecture
        try:
            broker = await initialize_message_broker("core-service")
            broker_initialized = True
            logger.info("Message broker initialized successfully")

            # Start message handler for ML service integration
            await message_handler.start_consuming()
            message_handler_started = True
            logger.info(
                "Message handler started successfully for ML service integration"
            )

        except Exception as e:
            logger.error(f"Message broker initialization failed: {str(e)}")
            logger.warning("Application will continue without event-driven features")

        startup_success = True
        logger.info("Application startup completed successfully")

    except Exception as e:
        logger.error(f"Critical error during application startup: {str(e)}")

        # Cleanup any partially initialized services
        if message_handler_started:
            try:
                await message_handler.stop_consuming()
            except Exception as cleanup_error:
                logger.error(
                    f"Error stopping message handler during startup cleanup: {cleanup_error}"
                )

        if broker_initialized:
            try:
                await cleanup_message_broker()
            except Exception as cleanup_error:
                logger.error(
                    f"Error cleaning up message broker during startup cleanup: {cleanup_error}"
                )

        if scheduler_initialized:
            try:
                scheduler.shutdown()
            except Exception as cleanup_error:
                logger.error(
                    f"Error shutting down scheduler during startup cleanup: {cleanup_error}"
                )

        raise

    # Application is running
    yield

    # Shutdown sequence
    logger.info("Starting application shutdown...")

    try:
        # Stop message handler first
        if message_handler_started:
            try:
                await message_handler.stop_consuming()
                logger.info("Message handler stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping message handler: {str(e)}")

        # Cleanup message broker
        if broker_initialized:
            try:
                await cleanup_message_broker()
                logger.info("Message broker cleanup completed successfully")
            except Exception as e:
                logger.error(f"Message broker cleanup failed: {str(e)}")

        # Shutdown scheduler last
        if scheduler_initialized:
            try:
                scheduler.shutdown()
                logger.info("Scheduler shutdown completed successfully")
            except Exception as e:
                logger.error(f"Scheduler shutdown failed: {str(e)}")

        logger.info("Application shutdown completed successfully")

    except Exception as e:
        logger.error(f"Error during application shutdown: {str(e)}")


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application instance.

    Returns:
        FastAPI: Configured application instance
    """
    # Get database session and application settings
    db = next(get_db())
    try:
        settings = SettingsService.get_settings(db)
        app_name = settings.app_name
    except Exception as e:
        logger.warning(f"Failed to load settings from database: {str(e)}")
        app_name = "Job Scraper Core Service"
    finally:
        db.close()

    # Create FastAPI application with lifespan handler
    app = FastAPI(
        title=app_name,
        description="Core service for job scraping and ML data processing",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Add middleware in correct order (reverse order of execution)
    _configure_middleware(app)

    # Include API routers
    app.include_router(api_router)

    return app


def _configure_middleware(app: FastAPI) -> None:
    """
    Configure middleware for the FastAPI application.
    Middleware is executed in reverse order of addition.

    Args:
        app: FastAPI application instance
    """
    # CORS middleware (executed last)
    # app.add_middleware(
    #     CORSMiddleware,
    #     allow_origins=CORS_ORIGINS,
    #     allow_credentials=True,
    #     allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    #     allow_headers=["*"],
    #     expose_headers=["*"],
    #     max_age=600,
    # )

    # Rate limiting middleware
    app.add_middleware(
        RateLimitMiddleware,
        protected_endpoints=PROTECTED_ENDPOINTS,
    )

    # Monitoring middleware (executed first)
    app.add_middleware(MonitoringMiddleware)
    app.add_middleware(PerformanceMiddleware, slow_request_threshold_ms=2000)
    app.add_middleware(CorrelationMiddleware)


# Create application instance
app = create_application()


if __name__ == "__main__":
    """
    Development server entry point.
    For production deployment, use a proper ASGI server like uvicorn or gunicorn.
    """
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
