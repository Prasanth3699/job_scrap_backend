# utils/redis_lock.py
import redis
from ..core.config import get_settings

settings = get_settings()

redis_client = redis.Redis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0, decode_responses=True
)


class RedisLock:
    @staticmethod
    def acquire_lock(lock_name: str, timeout: int = 3600) -> bool:
        """Acquire a lock with the given name"""
        return redis_client.set(f"lock:{lock_name}", "1", nx=True, ex=timeout)

    @staticmethod
    def release_lock(lock_name: str) -> bool:
        """Release the lock with the given name"""
        return redis_client.delete(f"lock:{lock_name}")

    @staticmethod
    def is_locked(lock_name: str) -> bool:
        """Check if a lock exists"""
        return bool(redis_client.get(f"lock:{lock_name}"))
