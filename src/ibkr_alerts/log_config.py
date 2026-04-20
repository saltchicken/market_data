import sys
import logging
from logging.handlers import RotatingFileHandler


def setup_logging():
    """Configures logging to both console and rotating files."""
    logger = logging.getLogger("ibkr_alerts")
    logger.setLevel(logging.INFO)

    # Formatter for the logs
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # 2. File Handler (General Logs) - Max 5MB per file, keep 3 backups
    file_handler = RotatingFileHandler(
        "ibkr_alerts.log", maxBytes=5 * 1024 * 1024, backupCount=3
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # 3. File Handler (Alerts Only)
    alert_file_handler = RotatingFileHandler(
        "ibkr_alerts_triggered.log", maxBytes=5 * 1024 * 1024, backupCount=3
    )
    alert_file_handler.setLevel(
        logging.WARNING
    )  # Alerts will be logged as WARNING or higher
    alert_file_handler.setFormatter(formatter)

    # Clear existing handlers to prevent duplicates if called consecutively
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(alert_file_handler)

    # Silence overly verbose ib_insync debug logs
    logging.getLogger("ib_insync").setLevel(logging.ERROR)
