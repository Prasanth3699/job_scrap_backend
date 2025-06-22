import redis
from app.core.config import get_settings


def create_redis_client():
    """
    Create and return a Redis client based on configuration
    """
    settings = get_settings()

    try:
        # Create Redis client with connection parameters
        redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD
            or None,  # Use None if password is empty string
            decode_responses=True,
            socket_timeout=5,  # 5 second timeout
            socket_connect_timeout=5,  # 5 second connection timeout
        )

        # Test the connection
        redis_client.ping()
        print("Redis connection successful")
        return redis_client

    except Exception as e:
        print(f"Redis connection error: {e}")
        raise


# Create a single Redis client instance
redis_client = create_redis_client()


# Alternative connection pool method
def create_redis_connection_pool():
    """
    Create a Redis connection pool
    """
    settings = get_settings()

    try:
        # Create connection pool
        pool = redis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
            max_connections=20,
        )

        # Create Redis client from pool
        redis_client = redis.Redis(connection_pool=pool)

        # Test connection
        redis_client.ping()
        print("Redis connection pool created successfully")

        return redis_client

    except Exception as e:
        print(f"Redis connection pool error: {e}")
        raise
