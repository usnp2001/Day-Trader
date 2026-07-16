import logging
import os
import datetime

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

# Custom Daily File Handler to write directly to logs/trading_platform_YYYY-MM-DD.log
class DailyFileHandler(logging.FileHandler):
    def __init__(self, directory="logs", prefix="trading_platform_", suffix=".log", encoding="utf-8"):
        self.directory = directory
        self.prefix = prefix
        self.suffix = suffix
        self.encoding = encoding
        os.makedirs(self.directory, exist_ok=True)
        
        self.current_date = datetime.date.today()
        filename = self._get_filename(self.current_date)
        super().__init__(filename, encoding=self.encoding)

    def _get_filename(self, date_obj):
        date_str = date_obj.strftime("%Y-%m-%d")
        return os.path.join(self.directory, f"{self.prefix}{date_str}{self.suffix}")

    def emit(self, record):
        now_date = datetime.date.today()
        if now_date != self.current_date:
            self.current_date = now_date
            self.close()
            self.baseFilename = os.path.abspath(self._get_filename(self.current_date))
            self.stream = self._open()
        super().emit(record)

file_handler = DailyFileHandler(encoding="utf-8")
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
logger.addHandler(file_handler)
