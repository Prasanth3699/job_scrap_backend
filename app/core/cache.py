"""
Advanced caching layer for the job scraper microservice.
Provides intelligent caching with TTL, invalidation, and cache warming strategies.
"""

import json
import time
import hashlib
from typing import Any, Dict, Optional, List, Callable, Union
from datetime import datetime, timedelta
from functools import wraps
import asyncio
import redis
from dataclasses import dataclass

from ..core.logger import logger
from ..core.config import get_settings

settings = get_settings()


@dataclass
class CacheConfig:
    """Cache configuration settings"""
    
    # Default TTL values (in seconds)
    DEFAULT_TTL = 300  # 5 minutes
    SHORT_TTL = 60     # 1 minute
    MEDIUM_TTL = 900   # 15 minutes
    LONG_TTL = 3600    # 1 hour
    VERY_LONG_TTL = 86400  # 24 hours
    
    # Cache key prefixes
    JOB_PREFIX = "job:"
    USER_PREFIX = "user:"
    STATS_PREFIX = "stats:"
    SEARCH_PREFIX = "search:"
    INTERNAL_PREFIX = "internal:"
    
    # Cache settings
    MAX_KEY_LENGTH = 250
    COMPRESSION_THRESHOLD = 1024  # Compress values larger than 1KB


class CacheManager:
    """Advanced cache manager with Redis backend"""
    
    def __init__(self):
        self.config = CacheConfig()
        self.redis_client = None
        self.is_connected = False
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }
        
        # Initialize Redis connection
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection"""
        try:
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            self.redis_client.ping()
            self.is_connected = True
            logger.info("Cache manager connected to Redis")
            
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {str(e)}. Cache will be disabled.")
            self.redis_client = None
            self.is_connected = False
    
    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from prefix and arguments"""
        # Create a consistent key from arguments
        key_parts = [prefix]
        
        # Add positional arguments
        for arg in args:
            if isinstance(arg, (dict, list)):
                key_parts.append(json.dumps(arg, sort_keys=True))
            else:
                key_parts.append(str(arg))
        
        # Add keyword arguments
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            key_parts.append(json.dumps(sorted_kwargs, sort_keys=True))
        
        # Create hash if key is too long
        key = ":".join(key_parts)
        if len(key) > self.config.MAX_KEY_LENGTH:
            key_hash = hashlib.md5(key.encode()).hexdigest()
            key = f"{prefix}:hash:{key_hash}"
        
        return key
    
    def _serialize_value(self, value: Any) -> str:
        """Serialize value for storage"""
        try:
            serialized = json.dumps(value, default=str)
            
            # Compress large values
            if len(serialized) > self.config.COMPRESSION_THRESHOLD:
                import gzip
                import base64
                compressed = gzip.compress(serialized.encode('utf-8'))
                return f"gzip:{base64.b64encode(compressed).decode('ascii')}"
            
            return serialized
            
        except Exception as e:
            logger.error(f"Error serializing cache value: {str(e)}")
            raise
    
    def _deserialize_value(self, value: str) -> Any:
        """Deserialize value from storage"""
        try:
            # Handle compressed values
            if value.startswith("gzip:"):
                import gzip
                import base64
                compressed_data = base64.b64decode(value[5:].encode('ascii'))
                decompressed = gzip.decompress(compressed_data).decode('utf-8')
                return json.loads(decompressed)
            
            return json.loads(value)
            
        except Exception as e:
            logger.error(f"Error deserializing cache value: {str(e)}")
            raise
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.is_connected:
            return None
        
        try:
            value = self.redis_client.get(key)
            if value is not None:
                self.cache_stats["hits"] += 1
                return self._deserialize_value(value)
            else:
                self.cache_stats["misses"] += 1
                return None
                
        except Exception as e:
            self.cache_stats["errors"] += 1
            logger.error(f"Cache get error for key {key}: {str(e)}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache with TTL"""
        if not self.is_connected:
            return False
        
        try:
            ttl = ttl or self.config.DEFAULT_TTL
            serialized_value = self._serialize_value(value)
            
            result = self.redis_client.setex(key, ttl, serialized_value)
            if result:
                self.cache_stats["sets"] += 1
            return result
            
        except Exception as e:
            self.cache_stats["errors"] += 1
            logger.error(f"Cache set error for key {key}: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.is_connected:
            return False
        
        try:
            result = self.redis_client.delete(key)
            if result:
                self.cache_stats["deletes"] += 1
            return bool(result)
            
        except Exception as e:
            self.cache_stats["errors"] += 1
            logger.error(f"Cache delete error for key {key}: {str(e)}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self.is_connected:
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                self.cache_stats["deletes"] += deleted
                return deleted
            return 0
            
        except Exception as e:
            self.cache_stats["errors"] += 1
            logger.error(f"Cache delete pattern error for pattern {pattern}: {str(e)}")
            return 0
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if not self.is_connected:
            return False
        
        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            self.cache_stats["errors"] += 1
            logger.error(f"Cache exists error for key {key}: {str(e)}")
            return False
    
    def get_ttl(self, key: str) -> int:
        """Get remaining TTL for key"""
        if not self.is_connected:
            return -1
        
        try:
            return self.redis_client.ttl(key)
        except Exception as e:
            self.cache_stats["errors"] += 1
            logger.error(f"Cache TTL error for key {key}: {str(e)}")
            return -1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = self.cache_stats.copy()
        
        # Calculate hit rate
        total_requests = stats["hits"] + stats["misses"]
        hit_rate = (stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        stats.update({
            "hit_rate_percent": round(hit_rate, 2),
            "total_requests": total_requests,
            "connected": self.is_connected,
            "redis_info": self._get_redis_info() if self.is_connected else None
        })
        
        return stats
    
    def _get_redis_info(self) -> Dict[str, Any]:
        """Get Redis server information"""
        try:
            info = self.redis_client.info()
            return {
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0)
            }
        except Exception as e:
            logger.error(f"Error getting Redis info: {str(e)}")
            return {"error": str(e)}
    
    def clear_all(self) -> bool:
        """Clear all cache data (use with caution!)"""
        if not self.is_connected:
            return False
        
        try:
            self.redis_client.flushdb()
            logger.warning("All cache data has been cleared")
            return True
        except Exception as e:
            self.cache_stats["errors"] += 1
            logger.error(f"Error clearing cache: {str(e)}")
            return False


# Global cache manager instance
cache_manager = CacheManager()


# Caching decorators
def cached(
    prefix: str,
    ttl: int = None,
    key_func: Callable = None
):
    """
    Decorator for caching function results.
    
    Args:
        prefix: Cache key prefix
        ttl: Time to live in seconds
        key_func: Function to generate cache key from arguments
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = cache_manager._generate_cache_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            if result is not None:
                cache_manager.set(cache_key, result, ttl)
                logger.debug(f"Cached result for key: {cache_key}")
            
            return result
        
        return wrapper
    return decorator


def cached_async(
    prefix: str,
    ttl: int = None,
    key_func: Callable = None
):
    """
    Async version of the cached decorator.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = cache_manager._generate_cache_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            if result is not None:
                cache_manager.set(cache_key, result, ttl)
                logger.debug(f"Cached result for key: {cache_key}")
            
            return result
        
        return wrapper
    return decorator


# Specialized caching functions for common use cases
class JobCache:
    """Specialized caching for job-related data"""
    
    @staticmethod
    def get_job(job_id: int) -> Optional[Dict]:
        """Get cached job data"""
        key = cache_manager._generate_cache_key(CacheConfig.JOB_PREFIX, job_id)
        return cache_manager.get(key)
    
    @staticmethod
    def set_job(job_id: int, job_data: Dict, ttl: int = CacheConfig.MEDIUM_TTL) -> bool:
        """Cache job data"""
        key = cache_manager._generate_cache_key(CacheConfig.JOB_PREFIX, job_id)
        return cache_manager.set(key, job_data, ttl)
    
    @staticmethod
    def delete_job(job_id: int) -> bool:
        """Remove job from cache"""
        key = cache_manager._generate_cache_key(CacheConfig.JOB_PREFIX, job_id)
        return cache_manager.delete(key)
    
    @staticmethod
    def get_job_search(search_params: Dict) -> Optional[Dict]:
        """Get cached job search results"""
        key = cache_manager._generate_cache_key(CacheConfig.SEARCH_PREFIX, **search_params)
        return cache_manager.get(key)
    
    @staticmethod
    def set_job_search(search_params: Dict, results: Dict, ttl: int = CacheConfig.SHORT_TTL) -> bool:
        """Cache job search results"""
        key = cache_manager._generate_cache_key(CacheConfig.SEARCH_PREFIX, **search_params)
        return cache_manager.set(key, results, ttl)
    
    @staticmethod
    def invalidate_job_searches() -> int:
        """Invalidate all job search caches"""
        pattern = f"{CacheConfig.SEARCH_PREFIX}*"
        return cache_manager.delete_pattern(pattern)


class StatsCache:
    """Specialized caching for statistics and metrics"""
    
    @staticmethod
    def get_dashboard_stats() -> Optional[Dict]:
        """Get cached dashboard statistics"""
        key = cache_manager._generate_cache_key(CacheConfig.STATS_PREFIX, "dashboard")
        return cache_manager.get(key)
    
    @staticmethod
    def set_dashboard_stats(stats: Dict, ttl: int = CacheConfig.MEDIUM_TTL) -> bool:
        """Cache dashboard statistics"""
        key = cache_manager._generate_cache_key(CacheConfig.STATS_PREFIX, "dashboard")
        return cache_manager.set(key, stats, ttl)
    
    @staticmethod
    def get_job_stats() -> Optional[Dict]:
        """Get cached job statistics"""
        key = cache_manager._generate_cache_key(CacheConfig.STATS_PREFIX, "jobs")
        return cache_manager.get(key)
    
    @staticmethod
    def set_job_stats(stats: Dict, ttl: int = CacheConfig.LONG_TTL) -> bool:
        """Cache job statistics"""
        key = cache_manager._generate_cache_key(CacheConfig.STATS_PREFIX, "jobs")
        return cache_manager.set(key, stats, ttl)


class InternalCache:
    """Caching for internal API responses"""
    
    @staticmethod
    def get_bulk_jobs(params: Dict) -> Optional[Dict]:
        """Get cached bulk jobs data"""
        key = cache_manager._generate_cache_key(CacheConfig.INTERNAL_PREFIX, "bulk_jobs", **params)
        return cache_manager.get(key)
    
    @staticmethod
    def set_bulk_jobs(params: Dict, data: Dict, ttl: int = CacheConfig.MEDIUM_TTL) -> bool:
        """Cache bulk jobs data"""
        key = cache_manager._generate_cache_key(CacheConfig.INTERNAL_PREFIX, "bulk_jobs", **params)
        return cache_manager.set(key, data, ttl)
    
    @staticmethod
    def get_categories() -> Optional[List[str]]:
        """Get cached job categories"""
        key = cache_manager._generate_cache_key(CacheConfig.INTERNAL_PREFIX, "categories")
        return cache_manager.get(key)
    
    @staticmethod
    def set_categories(categories: List[str], ttl: int = CacheConfig.VERY_LONG_TTL) -> bool:
        """Cache job categories"""
        key = cache_manager._generate_cache_key(CacheConfig.INTERNAL_PREFIX, "categories")
        return cache_manager.set(key, categories, ttl)
    
    @staticmethod
    def get_locations() -> Optional[List[str]]:
        """Get cached job locations"""
        key = cache_manager._generate_cache_key(CacheConfig.INTERNAL_PREFIX, "locations")
        return cache_manager.get(key)
    
    @staticmethod
    def set_locations(locations: List[str], ttl: int = CacheConfig.VERY_LONG_TTL) -> bool:
        """Cache job locations"""
        key = cache_manager._generate_cache_key(CacheConfig.INTERNAL_PREFIX, "locations")
        return cache_manager.set(key, locations, ttl)
    
    @staticmethod
    def get_job_data(job_id: int) -> Optional[Dict]:
        """Get cached job data for ML service"""
        key = cache_manager._generate_cache_key(CacheConfig.INTERNAL_PREFIX, "job_data", job_id)
        return cache_manager.get(key)
    
    @staticmethod
    def set_job_data(job_id: int, job_data: Dict, ttl: int = CacheConfig.MEDIUM_TTL) -> bool:
        """Cache job data for ML service"""
        key = cache_manager._generate_cache_key(CacheConfig.INTERNAL_PREFIX, "job_data", job_id)
        return cache_manager.set(key, job_data, ttl)


# Cache invalidation helpers
def invalidate_job_caches(job_id: int = None):
    """Invalidate job-related caches"""
    if job_id:
        JobCache.delete_job(job_id)
    
    # Invalidate search results and stats
    JobCache.invalidate_job_searches()
    cache_manager.delete_pattern(f"{CacheConfig.STATS_PREFIX}*")
    
    logger.info(f"Invalidated job caches" + (f" for job {job_id}" if job_id else ""))


def warm_cache():
    """Warm up frequently accessed cache entries"""
    logger.info("Starting cache warming...")
    
    # This would typically be called on application startup
    # to pre-populate cache with frequently accessed data
    
    try:
        # Example: Pre-cache job categories and locations
        # You would call your actual service methods here
        pass
        
    except Exception as e:
        logger.error(f"Error during cache warming: {str(e)}")


# Health check for cache
def get_cache_health() -> Dict[str, Any]:
    """Get cache system health information"""
    return {
        "connected": cache_manager.is_connected,
        "stats": cache_manager.get_stats(),
        "timestamp": datetime.now().isoformat()
    }