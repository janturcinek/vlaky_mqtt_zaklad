import logging
from logging.handlers import RotatingFileHandler
import os
from nastaveni import DevelopmentConfig

LOG_FILE = os.path.join(os.path.dirname(DevelopmentConfig.DATABASE), "app_error.log")

_logger = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=2 * 1024 * 1024,  # 2 MB
        backupCount=3,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    logger = logging.getLogger("app")
    logger.setLevel(logging.ERROR)
    logger.addHandler(handler)

    _logger = logger
    return _logger
