from functools import wraps
from time import sleep
from loguru import logger
from ..core.constants import MAX_RETRIES, RETRY_DELAY


def retry_on_exception(retries=MAX_RETRIES, delay=RETRY_DELAY):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"Attempt {attempt + 1}/{retries} failed: {str(e)}")
                    if attempt < retries - 1:
                        sleep(delay)
            raise last_exception

        return wrapper

    return decorator


def log_execution_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        import time

        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            end_time = time.time()
            logger.info(
                f"Function {func.__name__} took {end_time - start_time:.2f} seconds"
            )
            return result
        except Exception as e:
            end_time = time.time()
            logger.error(
                f"Function {func.__name__} failed after {end_time - start_time:.2f} seconds: {str(e)}"
            )
            raise

    return wrapper
