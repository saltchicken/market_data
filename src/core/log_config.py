import sys
import logging
from logging.handlers import RotatingFileHandler


def setup_logging(app_name: str, log_level=logging.INFO):
    """Configures centralized root logging to console and rotating files."""
    
    # Target the root logger so all modules inherit these settings
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to prevent duplicates if called consecutively
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Formatter for the logs (now includes the specific module name)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s", 
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # 2. File Handler (General Logs) - Max 5MB per file, keep 3 backups
    file_handler = RotatingFileHandler(
        f"{app_name}.log", maxBytes=5 * 1024 * 1024, backupCount=3
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # 3. File Handler (Alerts Only)
    alert_file_handler = RotatingFileHandler(
        f"{app_name}_warnings.log", maxBytes=5 * 1024 * 1024, backupCount=3
    )
    alert_file_handler.setLevel(logging.WARNING)  # WARNING or higher
    alert_file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(alert_file_handler)

    # Silence overly verbose external library logs
    logging.getLogger("ib_insync").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    return root_logger
