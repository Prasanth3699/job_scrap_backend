import uuid
import time


class RedisLockManager:
    def __init__(self, redis_client):
        self.redis_client = redis_client

    def acquire_lock(
        self, lock_name: str, expire: int = 3600, timeout: int = 10
    ) -> bool:
        """
        Attempt to acquire a distributed lock

        :param lock_name: Unique lock identifier
        :param expire: Lock expiration time in seconds
        :param timeout: Maximum time to wait for lock
        :return: Boolean indicating lock acquisition
        """
        # Generate a unique token for this lock attempt
        lock_value = str(uuid.uuid4())

        # Track start time for timeout
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Attempt to set the lock with NX (only if not exists) and EX (expiration)
                acquired = self.redis_client.set(
                    lock_name,
                    lock_value,
                    nx=True,  # Only set if not exists
                    ex=expire,  # Expire after specified seconds
                )

                if acquired:
                    return True

                # Wait a bit before retrying
                time.sleep(0.1)

            except Exception as e:
                print(f"Error acquiring lock {lock_name}: {e}")
                return False

        return False

    def release_lock(self, lock_name: str) -> bool:
        """
        Release a previously acquired lock

        :param lock_name: Lock identifier to release
        :return: Boolean indicating successful release
        """
        try:
            return bool(self.redis_client.delete(lock_name))
        except Exception as e:
            print(f"Error releasing lock {lock_name}: {e}")
            return False

    def is_locked(self, lock_name: str) -> bool:
        """
        Check if a lock exists

        :param lock_name: Lock identifier to check
        :return: Boolean indicating lock status
        """
        try:
            return bool(self.redis_client.exists(lock_name))
        except Exception as e:
            print(f"Error checking lock {lock_name}: {e}")
            return False


# Import and create lock manager
from app.core.redis_config import redis_client

redis_lock_manager = RedisLockManager(redis_client)
