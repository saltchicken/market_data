import sys
import logging
from logging.handlers import RotatingFileHandler


# TODO: Remove the need for app_name parameter
def setup_logging(app_name: str = None, log_level=logging.INFO):
    """Configures centralized root logging to console and a single unified rotating file."""

    # Target the root logger so all modules inherit these settings
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to prevent duplicates if called consecutively
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Formatter for the logs (%(name)-20s already captures the module name!)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # 2. File Handler (General Logs) - Unified file for all modules and levels
    file_handler = RotatingFileHandler(
        "market_pipeline.log", maxBytes=5 * 1024 * 1024, backupCount=3
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Silence overly verbose external library logs
    logging.getLogger("ib_insync").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return root_logger
