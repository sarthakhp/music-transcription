import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from api.config import settings


def setup_logging():
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            RotatingFileHandler(
                settings.log_file,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8"
            )
        ]
    )
    
    logger = logging.getLogger("api")
    logger.info(f"Logging initialized - Level: {settings.log_level}")
    logger.info(f"Log file: {settings.log_file}")
    
    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"api.{name}")

