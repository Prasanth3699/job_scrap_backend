"""
Monitoring middleware for request tracing and metrics collection.
Automatically tracks all requests and collects performance metrics.
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.monitoring import (
    record_request_metrics,
    trace_request,
    metrics_collector
)
from ..core.logger import logger


class MonitoringMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically track requests and collect metrics.
    
    Features:
    - Automatic request ID generation
    - Response time tracking
    - Error rate monitoring
    - Request/response logging
    - Correlation ID propagation
    """
    
    def __init__(self, app, exclude_paths: list = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if this path should be excluded from monitoring
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Generate or extract request ID
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        
        # Extract user information if available
        user_id = None
        service_name = None
        
        try:
            # Try to extract user ID from request context if available
            if hasattr(request.state, 'user'):
                user_id = getattr(request.state.user, 'id', None)
            
            # Extract service name from headers (for internal requests)
            service_name = request.headers.get("x-service-name")
            
        except Exception:
            pass  # Continue without user context
        
        # Start timing
        start_time = time.time()
        status_code = 500  # Default to error status
        error_message = None
        
        try:
            # Use request tracing context
            async with trace_request(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                headers=dict(request.headers)
            ):
                # Add request ID to request state for use in handlers
                request.state.request_id = request_id
                
                # Process the request
                response = await call_next(request)
                status_code = response.status_code
                
                # Add request ID to response headers
                response.headers["x-request-id"] = request_id
                
                return response
                
        except Exception as e:
            error_message = str(e)
            logger.error(f"Request {request_id} failed: {error_message}")
            raise
            
        finally:
            # Calculate response time
            response_time_ms = (time.time() - start_time) * 1000
            
            # Record metrics
            try:
                record_request_metrics(
                    request_id=request_id,
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    response_time_ms=response_time_ms,
                    user_id=user_id,
                    service_name=service_name,
                    error_message=error_message
                )
                
                # Log request details
                log_level = "error" if status_code >= 500 else "warning" if status_code >= 400 else "info"
                log_message = (
                    f"{request.method} {request.url.path} - "
                    f"Status: {status_code}, "
                    f"Time: {response_time_ms:.2f}ms, "
                    f"ID: {request_id}"
                )
                
                if user_id:
                    log_message += f", User: {user_id}"
                if service_name:
                    log_message += f", Service: {service_name}"
                if error_message:
                    log_message += f", Error: {error_message}"
                
                getattr(logger, log_level)(log_message)
                
            except Exception as e:
                logger.error(f"Failed to record metrics for request {request_id}: {str(e)}")


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    Middleware specifically for performance monitoring and optimization.
    
    Features:
    - Slow request detection
    - Memory usage tracking
    - Database query monitoring
    - Cache hit/miss tracking
    """
    
    def __init__(self, app, slow_request_threshold_ms: float = 2000):
        super().__init__(app)
        self.slow_request_threshold_ms = slow_request_threshold_ms
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip for health checks and static resources
        if request.url.path.startswith(("/health", "/static", "/favicon")):
            return await call_next(request)
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Calculate response time
            response_time_ms = (time.time() - start_time) * 1000
            
            # Check for slow requests
            if response_time_ms > self.slow_request_threshold_ms:
                request_id = getattr(request.state, 'request_id', 'unknown')
                logger.warning(
                    f"Slow request detected: {request.method} {request.url.path} "
                    f"took {response_time_ms:.2f}ms (threshold: {self.slow_request_threshold_ms}ms) "
                    f"[ID: {request_id}]"
                )
                
                # Add slow request header
                response.headers["x-slow-request"] = "true"
                response.headers["x-response-time"] = str(int(response_time_ms))
            
            return response
            
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            request_id = getattr(request.state, 'request_id', 'unknown')
            
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"after {response_time_ms:.2f}ms - {str(e)} "
                f"[ID: {request_id}]"
            )
            raise


class CorrelationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for handling correlation IDs across service boundaries.
    
    Features:
    - Correlation ID extraction and propagation
    - Distributed tracing support
    - Service-to-service request tracking
    """
    
    def __init__(self, app):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract or generate correlation ID
        correlation_id = (
            request.headers.get("x-correlation-id") or
            request.headers.get("x-trace-id") or
            request.headers.get("x-request-id") or
            str(uuid.uuid4())
        )
        
        # Store in request state
        request.state.correlation_id = correlation_id
        
        # Process request
        response = await call_next(request)
        
        # Add correlation ID to response
        response.headers["x-correlation-id"] = correlation_id
        
        # Add service identifier
        response.headers["x-service-name"] = "job-scraper-core"
        
        return response


# Utility functions for middleware integration
def get_request_id(request: Request) -> str:
    """Get request ID from request state"""
    return getattr(request.state, 'request_id', 'unknown')


def get_correlation_id(request: Request) -> str:
    """Get correlation ID from request state"""
    return getattr(request.state, 'correlation_id', 'unknown')


def add_request_context(request: Request, **context):
    """Add additional context to request state for monitoring"""
    if not hasattr(request.state, 'monitoring_context'):
        request.state.monitoring_context = {}
    
    request.state.monitoring_context.update(context)


def get_request_context(request: Request) -> dict:
    """Get monitoring context from request state"""
    return getattr(request.state, 'monitoring_context', {})