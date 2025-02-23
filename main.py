from fastapi import FastAPI
from app.services.settings_service import SettingsService
from app.services.scheduler_service import init_scheduler, scheduler
from app.api.router import api_router
from app.db.session import get_db
from app.core.logger import logger
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()


ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]


def get_application():
    db = next(get_db())
    settings = SettingsService.get_settings(db)

    app = FastAPI(title=settings.app_name)
    app.include_router(api_router)

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ORIGINS,  # Allow requests from your Next.js app
        allow_credentials=True,
        allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
        allow_headers=["*"],  # Allow all headers
        expose_headers=["*"],
        max_age=600,  # Cache preflight requests for 10 minutes
    )

    @app.on_event("startup")
    async def startup_event():
        try:
            logger.info("Starting up the application...")
            init_scheduler()
            logger.info("Application startup completed successfully")
        except Exception as e:
            logger.error(f"Error during startup: {str(e)}")
            raise

    @app.on_event("shutdown")
    async def shutdown_event():
        try:
            logger.info("Shutting down the application...")
            scheduler.shutdown()
            logger.info("Application shutdown completed successfully")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")
            raise

    return app


app = get_application()


# from fastapi import FastAPI
# from app.core.config import get_settings
# from app.services.scheduler_service import init_scheduler, scheduler
# from app.api.router import api_router
# from app.db.base import Base
# from app.db.session import engine
# from app.core.logger import logger

# settings = get_settings()


# # Create database tables
# def init_db():
#     try:
#         Base.metadata.create_all(bind=engine)
#         logger.info("Database tables created successfully")
#     except Exception as e:
#         logger.error(f"Error creating database tables: {e}")
#         raise


# app = FastAPI(title=settings.APP_NAME)

# # Include API router
# app.include_router(api_router)


# @app.on_event("startup")
# async def startup_event():
#     """Initialize services on startup"""
#     try:
#         logger.info("Starting up the application...")
#         init_db()  # Initialize database
#         init_scheduler()
#         scheduler.start()
#         logger.info("Application startup completed successfully")
#     except Exception as e:
#         logger.error(f"Error during startup: {str(e)}")
#         raise


# @app.on_event("shutdown")
# async def shutdown_event():
#     """Cleanup on shutdown"""
#     try:
#         logger.info("Shutting down the application...")
#         scheduler.shutdown()
#         logger.info("Application shutdown completed successfully")
#     except Exception as e:
#         logger.error(f"Error during shutdown: {str(e)}")
#         raise
