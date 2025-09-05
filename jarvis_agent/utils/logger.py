import logging
import sys
from uvicorn.config import LOGGING_CONFIG

def init_logger(settings):
    log_handler = logging.StreamHandler(stream=sys.stdout)
    log_handler.setFormatter(Formatter())
    logging.root.addHandler(log_handler)
    logging.root.setLevel(settings.log_level)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    LOGGING_CONFIG["loggers"]["uvicorn"]["level"] = "WARN"
    LOGGING_CONFIG["loggers"]["uvicorn.error"]["level"] = "WARN"
    LOGGING_CONFIG["loggers"]["uvicorn.access"]["level"] = "WARN"

class Formatter(logging.Formatter):
    @classmethod
    def _get_level_color(cls, level):
        if level >= logging.CRITICAL:
            return "\033[1;35m"  # Bright Magenta
        elif level >= logging.ERROR:
            return "\033[1;31m"  # Bright Red
        elif level >= logging.WARNING:
            return "\033[1;33m"  # Bright Yellow
        elif level >= logging.INFO:
            return "\033[1;32m"  # Bright Green
        elif level >= logging.DEBUG:
            return "\033[1;34m"  # Bright Blue
        else:
            return "\033[0m"  # Reset to default

    def format(self, record):
        record.levelname = f"{self._get_level_color(record.levelno)}{record.levelname}\033[0m"
        log_format = "%(asctime)-15s %(levelname)s %(message)s"
        return logging.Formatter(log_format).format(record)