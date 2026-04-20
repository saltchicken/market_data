import os
import sys
import datetime
import logging
from dotenv import load_dotenv
from ib_insync import IB

from .log_config import setup_logging
from .database import get_watchlist_targets_from_db
from .bars import subscribe_historical_bars

# Initialize a module-level logger
logger = logging.getLogger("ibkr_alerts")

def main():
    setup_logging()
    logger.info("Starting IBKR Alerts Module...")

    load_dotenv()
    db_url = os.getenv("DB_URL")

    # Fetch the rich watchlist including targets and previous closes
    watch_targets = get_watchlist_targets_from_db(db_url)

    if not watch_targets:
        logger.error("Watchlist is empty or could not be loaded from the database. Exiting.")
        sys.exit(1)

    logger.info(f"Loaded {len(watch_targets)} active tickers from the database:")
    for ticker, data in watch_targets.items():
        prev_close_str = f"${data['prev_close']:.2f}" if data['prev_close'] else "N/A"
        vol_str = f"{data['target_volume']:,.0f}" if data['target_volume'] else "None"
        buy_str = f"${data['target_buy']:.2f}" if data['target_buy'] else "None"
        sell_str = f"${data['target_sell']:.2f}" if data['target_sell'] else "None"
        
        logger.info(f"  -> {ticker}: Prev Close={prev_close_str} | Vol={vol_str} | Buy={buy_str} | Sell={sell_str}")

    if len(watch_targets) > 45:
        logger.warning("WARNING: You are close to IBKR's hard limit of 50 simultaneous historical requests.")

    ib = IB()

    try:
        ib.connect("127.0.0.1", 4002, clientId=1)
        logger.info("Successfully connected to IB Gateway.")
    except Exception as e:
        logger.error(f"Failed to connect to IB Gateway: {e}")
        sys.exit(1)

    # Pass the targets directly into the subscription manager
    live_bars = subscribe_historical_bars(ib, watch_targets)

    logger.info("All contracts subscribed. Listening for premarket/RTH candle closes...")

    stop_hour = 13
    stop_minute = 5

    try:
        while True:
            ib.sleep(60)
            now = datetime.datetime.now()

            if now.hour >= stop_hour and now.minute >= stop_minute:
                logger.info(f"⏰ Reached {stop_hour}:{stop_minute:02d}. Market is closed.")
                break

    except KeyboardInterrupt:
        logger.warning("🛑 Ctrl+C detected. Stopping data stream...")
    finally:
        if ib.isConnected():
            ib.disconnect()
            logger.info("🔌 Disconnected cleanly from IB Gateway. Goodbye!")

if __name__ == "__main__":
    main()
