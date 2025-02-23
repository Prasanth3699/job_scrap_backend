from fastapi import APIRouter
from .endpoints import jobs, auth, settings, stats

api_router = APIRouter()

# Add a common prefix for all API routes
api_router = APIRouter(prefix="api/v1")

# Include routers with their specific prefixes
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(stats.router, prefix="/stats", tags=["statistics"])
