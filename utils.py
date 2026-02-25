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

    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    logging.getLogger("ib_insync").setLevel(logging.WARNING)

    return logger


def _extract_symbol_from_error(contract, error_string):
    """
    Extracted symbol parsing logic to handle contract attributes
    and regex fallback cleanly.
    """
    if contract and hasattr(contract, "symbol") and contract.symbol:
        return contract.symbol

    match = re.search(r"symbol='([^']+)'", error_string)
    if match:
        return match.group(1)

    return None


def _append_bad_symbol(symbol, filename):
    """
    Extracted the file I/O operations for recording invalid symbols.
    """
    try:
        existing = set()
        try:
            with open(filename, "r") as f:
                existing = set(f.read().splitlines())
        except FileNotFoundError:
            pass

        if symbol not in existing:
            with open(filename, "a") as f:
                f.write(f"{symbol}\n")
    except Exception as e:
        logging.error(f"‼️ Failed to record bad symbol to file: {e}")


def create_error_handler(bad_symbols_file="bad_symbols.txt"):
    """
    Factory function that returns a callback for ib_insync error events.
    Catches 'Error 200: No security definition' and writes the symbol to a text file.
    """

    def on_error(reqId, errorCode, errorString, contract):
        if errorCode in [200, 201]:

            symbol = _extract_symbol_from_error(contract, errorString)

            if symbol:
                logging.error(
                    f"‼️ Trading permission denied or invalid security definition detected for {symbol}. "
                    f"Adding to {bad_symbols_file}"
                )
                _append_bad_symbol(symbol, bad_symbols_file)

    return on_error
