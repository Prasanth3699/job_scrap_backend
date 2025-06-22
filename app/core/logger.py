import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import sys

# --- Directory and file names ---
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
APP_LOG = LOG_DIR / "app.log"
ERROR_LOG = LOG_DIR / "error.log"

# --- Formatters ---
SIMPLE_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(process)d | %(threadName)s | %(message)s"
ERROR_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(process)d | %(threadName)s | %(pathname)s:%(lineno)d | %(funcName)s | %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"

simple_formatter = logging.Formatter(SIMPLE_FORMAT, datefmt=DATEFMT)
error_formatter = logging.Formatter(ERROR_FORMAT, datefmt=DATEFMT)

# --- Handlers ---
console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(simple_formatter)

file_all_handler = TimedRotatingFileHandler(
    filename=str(APP_LOG), when="midnight", backupCount=14, encoding="utf8"
)
file_all_handler.setLevel(logging.INFO)
file_all_handler.setFormatter(simple_formatter)

file_error_handler = TimedRotatingFileHandler(
    filename=str(ERROR_LOG), when="midnight", backupCount=30, encoding="utf8"
)
file_error_handler.setLevel(logging.ERROR)
file_error_handler.setFormatter(error_formatter)

# --- Logger setup ---
LOGGER_NAME = "myapp"
logger = logging.getLogger(LOGGER_NAME)
logger.setLevel(logging.DEBUG)  # Capture all logs at DEBUG and above

# Avoid duplicate handlers if this is imported multiple times
if not logger.handlers:
    logger.addHandler(console_handler)
    logger.addHandler(file_all_handler)
    logger.addHandler(file_error_handler)

# Don't propagate to root logger (avoids double logging)
logger.propagate = False

# --- Optionally: tune noisy library loggers ---
for noisy_logger in ("uvicorn", "gunicorn", "asyncio", "urllib3"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

# --- Usage Example ---
if __name__ == "__main__":
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    try:
        1 / 0
    except Exception:
        logger.error("An error occurred", exc_info=True)
