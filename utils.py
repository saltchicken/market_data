import logging


def setup_logging(log_filename="trading_bot.log"):
    """Configures file and console logging for the bot and ib_insync."""

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s] - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(log_filename)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Avoid adding duplicate handlers if the function is called twice
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    logging.getLogger("ib_insync").setLevel(
        logging.WARNING
    )  # Set logging to INFO if needed

    return logger
