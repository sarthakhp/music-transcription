import logging
import sys
from logging.handlers import RotatingFileHandler
from api.config import settings


class TraceIdFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        from api.middleware.context import get_trace_id
        record.trace_id = get_trace_id() or "no-trace"
        return super().format(record)


_LOG_FORMAT = "[%(trace_id)s] %(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    formatter = TraceIdFormatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        settings.log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    logger = logging.getLogger("api")
    logger.info(f"Logging initialized - Level: {settings.log_level}")
    logger.info(f"Log file: {settings.log_file}")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"api.{name}")
