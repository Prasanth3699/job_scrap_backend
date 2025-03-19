# app/utils/redis_lock.py
import uuid
import time
import redis
from app.core.redis_config import redis_client


class RedisLock:
    @classmethod
    def acquire_lock(
        cls,
        lock_name: str,
        expire: int = 3600,
        timeout: int = 10,
        redis_client: redis.Redis = redis_client,
    ) -> bool:
        """
        Distributed lock acquisition with advanced features
        """
        lock_value = str(uuid.uuid4())
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Atomic lock acquisition
                acquired = redis_client.set(
                    lock_name,
                    lock_value,
                    nx=True,  # Only set if not exists
                    ex=expire,  # Auto-expire
                )

                if acquired:
                    return True

                time.sleep(0.1)
            except Exception as e:
                print(f"Lock acquisition error: {e}")
                return False

        return False

    @classmethod
    def release_lock(
        cls, lock_name: str, redis_client: redis.Redis = redis_client
    ) -> bool:
        """
        Safe lock release
        """
        try:
            return bool(redis_client.delete(lock_name))
        except Exception as e:
            print(f"Lock release error: {e}")
            return False

    @classmethod
    def is_locked(
        cls, lock_name: str, redis_client: redis.Redis = redis_client
    ) -> bool:
        """
        Check lock status
        """
        try:
            return bool(redis_client.exists(lock_name))
        except Exception as e:
            print(f"Lock status check error: {e}")
            return False
