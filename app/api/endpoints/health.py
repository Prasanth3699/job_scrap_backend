"""
Comprehensive health check endpoints for production monitoring.
Provides detailed health information about all system components.
"""

import asyncio
import time
import psutil
import os
from datetime import datetime, timezone
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from ...db.session import get_db
from ...core.logger import logger
from ...core.config import get_settings
from ...core.service_auth import check_service_auth_health

settings = get_settings()

router = APIRouter()


class HealthStatus(BaseModel):
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: datetime
    uptime_seconds: int
    version: str = "1.0.0"


class ComponentHealth(BaseModel):
    name: str
    status: str
    latency_ms: int
    details: Dict[str, Any]
    last_check: datetime


class DetailedHealthResponse(BaseModel):
    overall_status: str
    service_info: Dict[str, Any]
    components: List[ComponentHealth]
    system_metrics: Dict[str, Any]
    timestamp: datetime


# Application start time for uptime calculation
app_start_time = time.time()


@router.get("/", response_model=HealthStatus)
async def basic_health_check():
    """
    Basic health check endpoint for load balancers.
    Returns simple OK/NOT OK status.
    """
    try:
        uptime = int(time.time() - app_start_time)
        return HealthStatus(
            status="healthy",
            timestamp=datetime.now(timezone.utc),
            uptime_seconds=uptime,
        )
    except Exception as e:
        logger.error(f"Basic health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unavailable")


@router.get("/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(db: Session = Depends(get_db)):
    """
    Detailed health check for monitoring systems.
    Checks all components and provides comprehensive status.
    """
    try:
        components = []
        overall_healthy = True

        # Check database
        db_health = await check_database_health(db)
        components.append(db_health)
        if db_health.status != "healthy":
            overall_healthy = False

        # Check Redis cache
        redis_health = await check_redis_health()
        components.append(redis_health)
        if redis_health.status != "healthy":
            overall_healthy = False

        # Check service authentication
        auth_health = await check_auth_system_health()
        components.append(auth_health)
        if auth_health.status != "healthy":
            overall_healthy = False

        # Check external dependencies (if any)
        external_health = await check_external_dependencies()
        components.append(external_health)
        if external_health.status != "healthy":
            overall_healthy = False

        # System metrics
        system_metrics = get_system_metrics()

        # Service information
        service_info = {
            "name": "job-scraper-core",
            "version": "1.0.0",
            "environment": getattr(settings, "ENVIRONMENT", "unknown"),
            "uptime_seconds": int(time.time() - app_start_time),
            "process_id": os.getpid(),
            "python_version": f"{psutil.sys.version_info.major}.{psutil.sys.version_info.minor}",
        }

        overall_status = "healthy" if overall_healthy else "degraded"

        return DetailedHealthResponse(
            overall_status=overall_status,
            service_info=service_info,
            components=components,
            system_metrics=system_metrics,
            timestamp=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.error(f"Detailed health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Health check failed")


@router.get("/database")
async def database_health_check(db: Session = Depends(get_db)):
    """Database-specific health check"""
    db_health = await check_database_health(db)

    if db_health.status == "healthy":
        return db_health.dict()
    else:
        raise HTTPException(status_code=503, detail=db_health.dict())


@router.get("/cache")
async def cache_health_check():
    """Cache-specific health check"""
    redis_health = await check_redis_health()

    if redis_health.status == "healthy":
        return redis_health.dict()
    else:
        raise HTTPException(status_code=503, detail=redis_health.dict())


# Health check implementation functions
async def check_database_health(db: Session) -> ComponentHealth:
    """Check database connectivity and performance"""
    start_time = time.time()

    try:
        # Simple connectivity test
        result = db.execute(text("SELECT 1 as health_check")).fetchone()

        # More comprehensive checks
        job_count = db.execute(text("SELECT COUNT(*) FROM jobs")).scalar()
        active_connections = db.execute(
            text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
        ).scalar()

        latency_ms = int((time.time() - start_time) * 1000)

        details = {
            "connection": "ok",
            "query_result": result[0] if result else None,
            "total_jobs": job_count,
            "active_connections": active_connections,
            "database_url_configured": bool(settings.DATABASE_URL),
        }

        # Determine status based on performance
        if latency_ms > 1000:  # More than 1 second
            status = "degraded"
        else:
            status = "healthy"

        return ComponentHealth(
            name="database",
            status=status,
            latency_ms=latency_ms,
            details=details,
            last_check=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return ComponentHealth(
            name="database",
            status="unhealthy",
            latency_ms=int((time.time() - start_time) * 1000),
            details={"error": str(e), "connection": "failed"},
            last_check=datetime.now(timezone.utc),
        )


async def check_redis_health() -> ComponentHealth:
    """Check Redis cache connectivity"""
    start_time = time.time()

    try:
        from ...core.redis_config import redis_client

        # Test basic operations
        await asyncio.to_thread(redis_client.ping)
        await asyncio.to_thread(redis_client.set, "health_check", "ok", ex=10)
        result = await asyncio.to_thread(redis_client.get, "health_check")

        latency_ms = int((time.time() - start_time) * 1000)

        details = {
            "connection": "ok",
            "ping_result": "pong",
            "test_operation": "success" if result == b"ok" else "failed",
            "redis_url_configured": bool(getattr(settings, "REDIS_URL", None)),
        }

        status = "healthy" if latency_ms < 100 else "degraded"

        return ComponentHealth(
            name="redis_cache",
            status=status,
            latency_ms=latency_ms,
            details=details,
            last_check=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.warning(f"Redis health check failed: {str(e)}")
        return ComponentHealth(
            name="redis_cache",
            status="unhealthy",
            latency_ms=int((time.time() - start_time) * 1000),
            details={"error": str(e), "connection": "failed"},
            last_check=datetime.now(timezone.utc),
        )


async def check_auth_system_health() -> ComponentHealth:
    """Check authentication system health"""
    start_time = time.time()

    try:
        # Check service auth configuration
        auth_health = await check_service_auth_health()

        latency_ms = int((time.time() - start_time) * 1000)

        return ComponentHealth(
            name="authentication",
            status=auth_health.get("status", "unknown"),
            latency_ms=latency_ms,
            details=auth_health,
            last_check=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.error(f"Auth system health check failed: {str(e)}")
        return ComponentHealth(
            name="authentication",
            status="unhealthy",
            latency_ms=int((time.time() - start_time) * 1000),
            details={"error": str(e)},
            last_check=datetime.now(timezone.utc),
        )


async def check_external_dependencies() -> ComponentHealth:
    """Check external service dependencies"""
    start_time = time.time()

    try:
        # Check external services (currently none)
        external_services_healthy = True

        latency_ms = int((time.time() - start_time) * 1000)

        details = {
            "external_services_configured": 0,
            "external_services_healthy": 0,
            "note": "No external services currently configured",
        }

        status = "healthy"

        return ComponentHealth(
            name="external_dependencies",
            status=status,
            latency_ms=latency_ms,
            details=details,
            last_check=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.error(f"External dependencies health check failed: {str(e)}")
        return ComponentHealth(
            name="external_dependencies",
            status="unhealthy",
            latency_ms=int((time.time() - start_time) * 1000),
            details={"error": str(e)},
            last_check=datetime.now(timezone.utc),
        )


def get_system_metrics() -> Dict[str, Any]:
    """Get system performance metrics"""
    try:
        # CPU and memory metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # Process-specific metrics
        process = psutil.Process()
        process_memory = process.memory_info()
        process_cpu = process.cpu_percent()

        return {
            "system": {
                "cpu_usage_percent": cpu_percent,
                "memory_usage_percent": memory.percent,
                "memory_available_mb": memory.available // (1024 * 1024),
                "disk_usage_percent": disk.percent,
                "disk_free_gb": disk.free // (1024 * 1024 * 1024),
            },
            "process": {
                "cpu_usage_percent": process_cpu,
                "memory_usage_mb": process_memory.rss // (1024 * 1024),
                "memory_virtual_mb": process_memory.vms // (1024 * 1024),
                "threads": process.num_threads(),
                "open_files": len(process.open_files()),
            },
            "uptime_seconds": int(time.time() - app_start_time),
        }

    except Exception as e:
        logger.error(f"Error getting system metrics: {str(e)}")
        return {"error": str(e)}


@router.get("/readiness")
async def readiness_check(db: Session = Depends(get_db)):
    """
    Kubernetes readiness probe endpoint.
    Checks if the service is ready to handle requests.
    """
    try:
        # Check critical dependencies
        db.execute(text("SELECT 1")).fetchone()

        return {
            "status": "ready",
            "timestamp": datetime.now(timezone.utc),
            "checks": ["database"],
        }

    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service not ready")


@router.get("/liveness")
async def liveness_check():
    """
    Kubernetes liveness probe endpoint.
    Checks if the service is still alive and should not be restarted.
    """
    try:
        # Simple check that the service is running
        uptime = int(time.time() - app_start_time)

        return {
            "status": "alive",
            "timestamp": datetime.now(timezone.utc),
            "uptime_seconds": uptime,
        }

    except Exception as e:
        logger.error(f"Liveness check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service not alive")
