from fastapi import APIRouter
from .endpoints import jobs, auth, settings, stats, job_sources, profile

api_router = APIRouter()

# Add a common prefix for all API routes
api_router = APIRouter(prefix="/api/v1")

# Include routers with their specific prefixes
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])

api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(
    job_sources.router, prefix="/job-sources", tags=["job-sources"]
)
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(stats.router, prefix="/stats", tags=["statistics"])
