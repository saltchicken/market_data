import logging
import re


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


def create_error_handler(bad_symbols_file="bad_symbols.txt"):
    """
    Factory function that returns a callback for ib_insync error events.
    Prioritizes extraction refactoring to keep the main logic clean.
    It catches 'Error 200: No security definition' and writes the symbol to a text file.
    """

    def on_error(reqId, errorCode, errorString, contract):
        if errorCode == 200:
            symbol = None
            # Attempt to extract the symbol from the contract object
            if contract and hasattr(contract, "symbol") and contract.symbol:
                symbol = contract.symbol
            else:
                # Fallback: regex search the error string just in case the contract object is empty
                match = re.search(r"symbol='([^']+)'", errorString)
                if match:
                    symbol = match.group(1)

            if symbol:
                logging.error(
                    f"‼️ Invalid security definition detected for {symbol}. Adding to {bad_symbols_file}"
                )
                try:
                    # Read existing symbols to prevent duplicates in the text file
                    existing = set()
                    try:
                        with open(bad_symbols_file, "r") as f:
                            existing = set(f.read().splitlines())
                    except FileNotFoundError:
                        pass  # File doesn't exist yet, which is fine

                    if symbol not in existing:
                        with open(bad_symbols_file, "a") as f:
                            f.write(f"{symbol}\n")
                except Exception as e:
                    logging.error(f"‼️ Failed to record bad symbol to file: {e}")

    return on_error
