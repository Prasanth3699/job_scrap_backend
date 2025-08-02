"""
Advanced rate limiting middleware with Redis backend, multiple algorithms, and intelligent throttling.
Supports sliding window, token bucket, and adaptive rate limiting based on system load.
"""

import time
import json
import hashlib
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import redis
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.logger import logger
from ..core.config import get_settings
from ..core.monitoring import metrics_collector

settings = get_settings()


class RateLimitAlgorithm(Enum):
    """Available rate limiting algorithms"""

    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    FIXED_WINDOW = "fixed_window"
    ADAPTIVE = "adaptive"


@dataclass
class RateLimitRule:
    """Configuration for a rate limit rule"""

    requests_per_minute: int
    burst_size: int = None  # For token bucket
    window_size_seconds: int = 60
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW
    paths: List[str] = None  # Specific paths this rule applies to
    methods: List[str] = None  # HTTP methods
    user_based: bool = False  # Apply per user instead of per IP
    block_duration_seconds: int = 300  # How long to block after limit exceeded


class AdvancedRateLimiter:
    """Advanced rate limiter with multiple algorithms and Redis backend"""

    def __init__(self):
        self.redis_client = None
        self.fallback_storage = {}  # In-memory fallback
        self.use_redis = False

        # Default rules
        self.rules = {
            "default": RateLimitRule(
                requests_per_minute=100,
                burst_size=20,
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
            ),
            "auth": RateLimitRule(
                requests_per_minute=10,
                burst_size=5,
                algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
                paths=["/api/v1/auth/login", "/api/v1/auth/register"],
                block_duration_seconds=900,  # 15 minutes
            ),
            "api": RateLimitRule(
                requests_per_minute=200,
                burst_size=50,
                algorithm=RateLimitAlgorithm.ADAPTIVE,
                user_based=True,
            ),
            "internal": RateLimitRule(
                requests_per_minute=1000,
                burst_size=200,
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
                paths=["/api/v1/internal/"],
            ),
        }

        # Initialize Redis
        self._init_redis()

    def _init_redis(self):
        """Initialize Redis connection for distributed rate limiting"""
        try:
            redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )

            # Test connection
            self.redis_client.ping()
            self.use_redis = True
            logger.info("Rate limiter connected to Redis")

        except Exception as e:
            logger.warning(
                f"Rate limiter Redis connection failed: {str(e)}. Using in-memory fallback."
            )
            self.use_redis = False

    def _get_client_identifier(self, request: Request, rule: RateLimitRule) -> str:
        """Get client identifier for rate limiting"""
        if rule.user_based:
            # Try to get user ID from request state
            user_id = getattr(request.state, "user_id", None)
            if user_id:
                return f"user:{user_id}"

        # Fallback to IP address
        client_ip = request.client.host if request.client else "unknown"

        # Consider X-Forwarded-For header
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        return f"ip:{client_ip}"

    def _get_rate_limit_key(self, identifier: str, rule_name: str, path: str) -> str:
        """Generate rate limit key for storage"""
        # Create a shorter key by hashing long paths
        if len(path) > 50:
            path_hash = hashlib.md5(path.encode()).hexdigest()[:8]
            path = f"path:{path_hash}"

        return f"rate_limit:{rule_name}:{identifier}:{path}"

    def _get_applicable_rule(self, request: Request) -> Tuple[str, RateLimitRule]:
        """Determine which rate limit rule applies to this request"""
        path = request.url.path
        method = request.method

        # Check specific rules first
        for rule_name, rule in self.rules.items():
            if rule_name == "default":
                continue

            # Check path matching
            if rule.paths:
                if any(path.startswith(rule_path) for rule_path in rule.paths):
                    if not rule.methods or method in rule.methods:
                        return rule_name, rule

        # Check for internal service requests
        if path.startswith("/api/v1/internal/"):
            return "internal", self.rules["internal"]

        # Check for auth endpoints
        if any(auth_path in path for auth_path in ["/login", "/register", "/auth/"]):
            return "auth", self.rules["auth"]

        # Check for API endpoints (user-based)
        if path.startswith("/api/v1/"):
            user_id = getattr(request.state, "user_id", None)
            if user_id:
                return "api", self.rules["api"]

        return "default", self.rules["default"]

    async def check_rate_limit(self, request: Request) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request should be rate limited.
        Returns (is_allowed, rate_limit_info)
        """
        try:
            # Get applicable rule
            rule_name, rule = self._get_applicable_rule(request)

            # Get client identifier
            identifier = self._get_client_identifier(request, rule)

            # Generate key
            key = self._get_rate_limit_key(identifier, rule_name, request.url.path)

            # Apply rate limiting algorithm
            if rule.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
                return await self._sliding_window_check(key, rule)
            elif rule.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
                return await self._token_bucket_check(key, rule)
            elif rule.algorithm == RateLimitAlgorithm.FIXED_WINDOW:
                return await self._fixed_window_check(key, rule)
            elif rule.algorithm == RateLimitAlgorithm.ADAPTIVE:
                return await self._adaptive_check(key, rule, request)
            else:
                # Default to sliding window
                return await self._sliding_window_check(key, rule)

        except Exception as e:
            logger.error(f"Rate limit check error: {str(e)}")
            # Fail open - allow request if rate limiting fails
            return True, {"error": str(e)}

    async def _sliding_window_check(
        self, key: str, rule: RateLimitRule
    ) -> Tuple[bool, Dict[str, Any]]:
        """Sliding window rate limiting algorithm"""
        now = time.time()
        window_start = now - rule.window_size_seconds

        if self.use_redis:
            # Redis-based sliding window
            pipe = self.redis_client.pipeline()

            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)

            # Count current requests
            pipe.zcard(key)

            # Add current request
            pipe.zadd(key, {str(now): now})

            # Set expiry
            pipe.expire(key, rule.window_size_seconds + 1)

            results = pipe.execute()
            current_count = results[1]

        else:
            # In-memory fallback
            if key not in self.fallback_storage:
                self.fallback_storage[key] = []

            # Clean old entries
            self.fallback_storage[key] = [
                req_time
                for req_time in self.fallback_storage[key]
                if req_time > window_start
            ]

            current_count = len(self.fallback_storage[key])
            self.fallback_storage[key].append(now)

        is_allowed = current_count < rule.requests_per_minute

        return is_allowed, {
            "algorithm": "sliding_window",
            "limit": rule.requests_per_minute,
            "remaining": max(0, rule.requests_per_minute - current_count - 1),
            "reset_time": int(now + rule.window_size_seconds),
            "retry_after": rule.window_size_seconds if not is_allowed else None,
        }

    async def _token_bucket_check(
        self, key: str, rule: RateLimitRule
    ) -> Tuple[bool, Dict[str, Any]]:
        """Token bucket rate limiting algorithm"""
        now = time.time()
        bucket_size = rule.burst_size or rule.requests_per_minute
        refill_rate = rule.requests_per_minute / 60  # tokens per second

        if self.use_redis:
            # Redis-based token bucket
            bucket_data = self.redis_client.get(key)

            if bucket_data:
                bucket = json.loads(bucket_data)
                last_refill = bucket["last_refill"]
                tokens = bucket["tokens"]
            else:
                last_refill = now
                tokens = bucket_size

            # Refill tokens
            time_passed = now - last_refill
            tokens = min(bucket_size, tokens + (time_passed * refill_rate))

            is_allowed = tokens >= 1

            if is_allowed:
                tokens -= 1

            # Store updated bucket
            bucket_data = {"tokens": tokens, "last_refill": now}
            self.redis_client.setex(
                key, rule.window_size_seconds, json.dumps(bucket_data)
            )

        else:
            # In-memory fallback
            if key not in self.fallback_storage:
                self.fallback_storage[key] = {"tokens": bucket_size, "last_refill": now}

            bucket = self.fallback_storage[key]
            time_passed = now - bucket["last_refill"]
            bucket["tokens"] = min(
                bucket_size, bucket["tokens"] + (time_passed * refill_rate)
            )
            bucket["last_refill"] = now

            is_allowed = bucket["tokens"] >= 1

            if is_allowed:
                bucket["tokens"] -= 1

        return is_allowed, {
            "algorithm": "token_bucket",
            "limit": rule.requests_per_minute,
            "bucket_size": bucket_size,
            "tokens_remaining": (
                int(tokens)
                if "tokens" in locals()
                else int(self.fallback_storage[key]["tokens"])
            ),
            "refill_rate": refill_rate,
            "retry_after": int(1 / refill_rate) if not is_allowed else None,
        }

    async def _fixed_window_check(
        self, key: str, rule: RateLimitRule
    ) -> Tuple[bool, Dict[str, Any]]:
        """Fixed window rate limiting algorithm"""
        now = time.time()
        window_start = int(now // rule.window_size_seconds) * rule.window_size_seconds
        window_key = f"{key}:{int(window_start)}"

        if self.use_redis:
            # Redis-based fixed window
            current_count = self.redis_client.incr(window_key)
            if current_count == 1:
                self.redis_client.expire(window_key, rule.window_size_seconds)
        else:
            # In-memory fallback
            if window_key not in self.fallback_storage:
                self.fallback_storage[window_key] = 0
            self.fallback_storage[window_key] += 1
            current_count = self.fallback_storage[window_key]

        is_allowed = current_count <= rule.requests_per_minute

        return is_allowed, {
            "algorithm": "fixed_window",
            "limit": rule.requests_per_minute,
            "remaining": max(0, rule.requests_per_minute - current_count),
            "reset_time": int(window_start + rule.window_size_seconds),
            "retry_after": (
                int(window_start + rule.window_size_seconds - now)
                if not is_allowed
                else None
            ),
        }

    async def _adaptive_check(
        self, key: str, rule: RateLimitRule, request: Request
    ) -> Tuple[bool, Dict[str, Any]]:
        """Adaptive rate limiting based on system load"""
        # Get current system metrics
        try:
            metrics = metrics_collector.get_current_metrics()

            # Adjust rate limit based on system performance
            base_limit = rule.requests_per_minute

            # Reduce limit if error rate is high
            error_rate = metrics.get("requests", {}).get("error_rate_percent", 0)
            if error_rate > 10:
                base_limit = int(base_limit * 0.5)  # Reduce by 50%
            elif error_rate > 5:
                base_limit = int(base_limit * 0.75)  # Reduce by 25%

            # Reduce limit if response time is high
            avg_response_time = metrics.get("performance", {}).get(
                "avg_response_time_ms", 0
            )
            if avg_response_time > 2000:  # > 2 seconds
                base_limit = int(base_limit * 0.6)  # Reduce by 40%
            elif avg_response_time > 1000:  # > 1 second
                base_limit = int(base_limit * 0.8)  # Reduce by 20%

            # Reduce limit if CPU/memory is high
            system_metrics = metrics.get("system", {})
            if isinstance(system_metrics, dict) and "error" not in system_metrics:
                cpu_usage = system_metrics.get("cpu_usage_percent", 0)
                memory_usage = system_metrics.get("memory_usage_percent", 0)

                if cpu_usage > 80 or memory_usage > 85:
                    base_limit = int(base_limit * 0.5)  # Reduce by 50%
                elif cpu_usage > 60 or memory_usage > 70:
                    base_limit = int(base_limit * 0.75)  # Reduce by 25%

            # Ensure minimum limit
            adaptive_limit = max(5, base_limit)

            # Create temporary rule with adaptive limit
            adaptive_rule = RateLimitRule(
                requests_per_minute=adaptive_limit,
                window_size_seconds=rule.window_size_seconds,
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
            )

            # Use sliding window with adaptive limit
            is_allowed, info = await self._sliding_window_check(key, adaptive_rule)

            # Add adaptive information
            info.update(
                {
                    "algorithm": "adaptive",
                    "original_limit": rule.requests_per_minute,
                    "adaptive_limit": adaptive_limit,
                    "adjustment_factors": {
                        "error_rate": error_rate,
                        "avg_response_time": avg_response_time,
                        "system_load": {
                            "cpu": system_metrics.get("cpu_usage_percent", 0),
                            "memory": system_metrics.get("memory_usage_percent", 0),
                        },
                    },
                }
            )

            return is_allowed, info

        except Exception as e:
            logger.error(f"Adaptive rate limiting error: {str(e)}")
            # Fallback to normal sliding window
            return await self._sliding_window_check(key, rule)

    def get_rate_limit_stats(self) -> Dict[str, Any]:
        """Get rate limiting statistics"""
        stats = {
            "rules": {
                name: {
                    "requests_per_minute": rule.requests_per_minute,
                    "algorithm": rule.algorithm.value,
                    "paths": rule.paths,
                    "user_based": rule.user_based,
                }
                for name, rule in self.rules.items()
            },
            "backend": "redis" if self.use_redis else "memory",
            "timestamp": datetime.now().isoformat(),
        }

        if not self.use_redis:
            stats["memory_keys"] = len(self.fallback_storage)

        return stats


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Advanced rate limiting middleware"""

    def __init__(
        self,
        app,
        rate_limiter: AdvancedRateLimiter = None,
        protected_endpoints: Optional[List[str]] = None,
    ):
        super().__init__(app)
        self.rate_limiter = rate_limiter or AdvancedRateLimiter()

        # Paths to exclude from rate limiting
        self.excluded_paths = [
            "/health",
            "/readiness",
            "/liveness",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

        # If `protected_endpoints` is provided, only apply rate limiting to those paths
        self.protected_endpoints = protected_endpoints

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # If using `protected_endpoints`, skip rate limiting for all other paths
        if self.protected_endpoints is not None:
            if path not in self.protected_endpoints:
                return await call_next(request)
        else:
            # Skip rate limiting for excluded paths
            if any(path.startswith(excluded) for excluded in self.excluded_paths):
                return await call_next(request)

        # Rate limit as usual
        is_allowed, rate_limit_info = await self.rate_limiter.check_rate_limit(request)

        if not is_allowed:
            headers = {
                "X-RateLimit-Limit": str(rate_limit_info.get("limit", 0)),
                "X-RateLimit-Remaining": str(rate_limit_info.get("remaining", 0)),
                "X-RateLimit-Reset": str(rate_limit_info.get("reset_time", 0)),
            }
            if rate_limit_info.get("retry_after"):
                headers["Retry-After"] = str(int(rate_limit_info["retry_after"]))

            client_id = self.rate_limiter._get_client_identifier(
                request, self.rate_limiter.rules["default"]
            )
            logger.warning(
                f"Rate limit exceeded for {client_id} on {request.method} {path} "
                f"(algorithm: {rate_limit_info.get('algorithm', 'unknown')})"
            )

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": "Too many requests. Please try again later.",
                    "rate_limit_info": rate_limit_info,
                },
                headers=headers,
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(rate_limit_info.get("limit", 0))
        response.headers["X-RateLimit-Remaining"] = str(
            rate_limit_info.get("remaining", 0)
        )
        response.headers["X-RateLimit-Reset"] = str(
            rate_limit_info.get("reset_time", 0)
        )
        return response


# Global rate limiter instance
rate_limiter = AdvancedRateLimiter()
