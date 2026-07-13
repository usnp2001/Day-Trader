import logging
import os

# Create logs directory if not exists
os.makedirs("logs", exist_ok=True)

# Define log format
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Configure logger
logger = logging.getLogger("trading_platform")
logger.setLevel(logging.INFO)

# Clear existing handlers to avoid duplicates
if logger.hasHandlers():
    logger.handlers.clear()

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
logger.addHandler(console_handler)

# Daily Timed Rotating File Handler
from logging.handlers import TimedRotatingFileHandler

def custom_namer(default_name):
    directory, filename = os.path.split(default_name)
    parts = filename.split(".")
    # Expected filename from standard TimedRotatingFileHandler: trading_platform.log.YYYYMMDD
    if len(parts) >= 3:
        date_str = parts[-1]  # "YYYYMMDD"
        new_filename = f"trading_platform_{date_str}.log"
        return os.path.join(directory, new_filename)
    return default_name

file_handler = TimedRotatingFileHandler(
    filename="logs/trading_platform.log",
    when="midnight",
    interval=1,
    backupCount=30,
    encoding="utf-8"
)
file_handler.suffix = "%Y%m%d"
file_handler.namer = custom_namer
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
logger.addHandler(file_handler)
