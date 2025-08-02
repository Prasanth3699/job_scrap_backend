"""
Internal API endpoints for microservice communication.
These endpoints are secured and designed for service-to-service communication.
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

from ...db.session import get_db
from ...db.repositories.job_repository import JobRepository
from ...models.user import User
from ...models.user_profile import UserProfile
from ...schemas.job import JobResponse
from ...schemas.profile import UserProfileResponse
from ...core.service_auth import (
    ServiceAuth,
    verify_service_auth,
    require_jobs_read_scope,
    require_users_read_scope,
    require_jobs_write_scope,
)
from ...core.logger import logger
from ...core.constants import DEFAULT_LIMIT

router = APIRouter(prefix="/internal", tags=["internal"])


# Response models for internal APIs
class BulkJobsResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    page: int
    limit: int
    has_more: bool
    last_updated: datetime
    next_page_url: Optional[str] = None


class UserDataResponse(BaseModel):
    user_id: int
    email: str
    name: str
    is_active: bool
    created_at: datetime
    profile: Optional[UserProfileResponse] = None


class JobMatchResult(BaseModel):
    job_id: int
    user_id: int
    match_score: float
    match_reasons: List[str]
    ml_model_version: str
    processed_at: datetime


class ServiceHealthResponse(BaseModel):
    service: str
    status: str
    database: Dict[str, Any]
    cache: Dict[str, Any]
    timestamp: datetime
    uptime_seconds: int


# Job data endpoints for ML/LLM services
@router.get("/jobs/bulk", response_model=BulkJobsResponse)
async def get_jobs_bulk(
    request: Request,
    db: Session = Depends(get_db),
    service_auth: ServiceAuth = Depends(require_jobs_read_scope),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=1000, description="Items per page"),
    since: Optional[datetime] = Query(
        None, description="Get jobs updated since this timestamp"
    ),
    categories: Optional[List[str]] = Query(
        None, description="Filter by job categories"
    ),
    locations: Optional[List[str]] = Query(None, description="Filter by locations"),
    include_description: bool = Query(True, description="Include job descriptions"),
    fresh_only: bool = Query(False, description="Only jobs from last 7 days"),
):
    """
    Bulk job data endpoint for ML/LLM services.
    Returns paginated job data with filtering options.
    """
    try:
        logger.info(
            f"Bulk jobs request from {service_auth.service_name}, page={page}, limit={limit}"
        )

        repo = JobRepository(db)
        offset = (page - 1) * limit

        # Apply filters based on parameters
        filters = {}
        if since:
            filters["updated_since"] = since
        if categories:
            filters["categories"] = categories
        if locations:
            filters["locations"] = locations
        if fresh_only:
            filters["updated_since"] = datetime.now() - timedelta(days=7)

        # Get jobs with one extra to check for more pages
        jobs, total = repo.get_filtered_jobs(skip=offset, limit=limit + 1, **filters)

        # Check if there are more pages
        has_more = len(jobs) > limit
        if has_more:
            jobs = jobs[:limit]

        # Generate next page URL
        next_page_url = None
        if has_more:
            next_page_url = (
                f"{request.url.replace(query='')}?page={page + 1}&limit={limit}"
            )
            if since:
                next_page_url += f"&since={since.isoformat()}"

        # Remove descriptions if not requested (for performance)
        if not include_description:
            for job in jobs:
                job.description = None

        response = BulkJobsResponse(
            jobs=jobs,
            total=total,
            page=page,
            limit=limit,
            has_more=has_more,
            last_updated=datetime.utcnow(),
            next_page_url=next_page_url,
        )

        logger.info(f"Returned {len(jobs)} jobs to {service_auth.service_name}")
        return response

    except Exception as e:
        logger.error(f"Error in bulk jobs endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch jobs data")


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_for_service(
    job_id: int,
    db: Session = Depends(get_db),
    service_auth: ServiceAuth = Depends(require_jobs_read_scope),
):
    """Get specific job data for ML/LLM processing"""
    try:
        repo = JobRepository(db)
        job = repo.get_by_id(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        logger.info(f"Job {job_id} requested by {service_auth.service_name}")
        return job

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch job")


@router.get("/users/{user_id}", response_model=UserDataResponse)
async def get_user_for_service(
    user_id: int,
    db: Session = Depends(get_db),
    service_auth: ServiceAuth = Depends(require_users_read_scope),
    include_profile: bool = Query(True, description="Include user profile data"),
):
    """Get user data for ML/LLM services (recommendations, personalization)"""
    try:
        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get profile if requested
        profile = None
        if include_profile:
            profile = (
                db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
            )

        response = UserDataResponse(
            user_id=user.id,
            email=user.email,
            name=user.name,
            is_active=user.is_active,
            created_at=user.created_at,
            profile=profile,
        )

        logger.info(f"User {user_id} data requested by {service_auth.service_name}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch user")


@router.post("/jobs/{job_id}/match-results")
async def store_job_match_results(
    job_id: int,
    match_results: List[JobMatchResult],
    db: Session = Depends(get_db),
    service_auth: ServiceAuth = Depends(require_jobs_write_scope),
):
    """Store ML service job matching results"""
    try:
        # Verify job exists
        repo = JobRepository(db)
        job = repo.get_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Store results (implement based on your storage needs)
        # This could be a separate table for match results
        stored_results = []
        for result in match_results:
            # TODO: Implement match result storage
            # This might involve creating a new model/table
            stored_results.append(
                {
                    "job_id": result.job_id,
                    "user_id": result.user_id,
                    "match_score": result.match_score,
                    "stored_at": datetime.utcnow(),
                }
            )

        logger.info(
            f"Stored {len(match_results)} match results for job {job_id} from {service_auth.service_name}"
        )

        return {
            "status": "success",
            "job_id": job_id,
            "results_stored": len(stored_results),
            "processed_by": service_auth.service_name,
            "timestamp": datetime.utcnow(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error storing match results for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to store match results")


@router.get("/jobs/categories", response_model=List[str])
async def get_job_categories(
    db: Session = Depends(get_db),
    service_auth: ServiceAuth = Depends(require_jobs_read_scope),
):
    """Get all available job categories for ML/LLM services"""
    try:
        repo = JobRepository(db)
        categories = repo.get_distinct_categories()

        logger.info(f"Job categories requested by {service_auth.service_name}")
        return categories

    except Exception as e:
        logger.error(f"Error fetching job categories: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch categories")


@router.get("/jobs/locations", response_model=List[str])
async def get_job_locations(
    db: Session = Depends(get_db),
    service_auth: ServiceAuth = Depends(require_jobs_read_scope),
):
    """Get all available job locations for ML/LLM services"""
    try:
        repo = JobRepository(db)
        locations = repo.get_distinct_locations()

        logger.info(f"Job locations requested by {service_auth.service_name}")
        return locations

    except Exception as e:
        logger.error(f"Error fetching job locations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch locations")


@router.get("/health", response_model=ServiceHealthResponse)
async def internal_health_check(
    db: Session = Depends(get_db),
    service_auth: ServiceAuth = Depends(verify_service_auth),
):
    """Health check endpoint for internal services"""
    import time
    import psutil

    try:
        # Check database
        db_status = "healthy"
        try:
            db.execute(text("SELECT 1"))
            db_health = {"status": "healthy", "connection": "ok"}
        except Exception as e:
            db_status = "unhealthy"
            db_health = {"status": "unhealthy", "error": str(e)}

        # Check cache (Redis)
        cache_health = {"status": "not_configured"}
        try:
            from ...core.redis_config import redis_client

            redis_client.ping()
            cache_health = {"status": "healthy", "connection": "ok"}
        except Exception as e:
            cache_health = {"status": "unhealthy", "error": str(e)}

        # System metrics
        uptime = time.time() - psutil.boot_time()

        response = ServiceHealthResponse(
            service="job-scraper-core",
            status=db_status,
            database=db_health,
            cache=cache_health,
            timestamp=datetime.utcnow(),
            uptime_seconds=int(uptime),
        )

        return response

    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        raise HTTPException(status_code=500, detail="Health check failed")


# Development/testing endpoints
if __name__ == "__main__":
    # These endpoints are only available in development

    @router.get("/dev/tokens")
    async def get_development_tokens():
        """Get service tokens for development/testing"""
        from ...core.service_auth import generate_service_tokens

        return generate_service_tokens()
