import sys
from pathlib import Path
from loguru import logger
from .config import get_settings

settings = get_settings()

# Configure loguru logger
log_path = Path("logs")
log_path.mkdir(exist_ok=True)

logger.remove()  # Remove default handler

# Add console handler
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    level=settings.LOG_LEVEL,
)

# Add file handler
logger.add(
    log_path / "app.log",
    rotation="1 day",
    retention="7 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    level=settings.LOG_LEVEL,
)
