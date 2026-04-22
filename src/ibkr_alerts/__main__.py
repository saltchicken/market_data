import os
import sys
import datetime
import logging
from dotenv import load_dotenv
from ib_insync import IB

from core.log_config import setup_logging
from .database import get_watchlist_targets_from_db
from .bars import monitor_market_open

logger = logging.getLogger("ibkr_alerts")


def main():
    setup_logging("ibkr_alerts")
    logger.info("Starting IBKR Market Open Monitor...")

    load_dotenv()
    db_url = os.getenv("DB_URL")

    # Fetch the watchlist and previous closes
    watch_targets = get_watchlist_targets_from_db(db_url)

    if not watch_targets:
        logger.error("Watchlist is empty or could not be loaded from the database. Exiting.")
        sys.exit(1)

    logger.info(f"Loaded {len(watch_targets)} active tickers from the database to monitor:")
    for ticker, data in watch_targets.items():
        prev_close_str = f"${data['prev_close']:.2f}" if data.get("prev_close") else "N/A"
        logger.info(f"  -> {ticker}: Prev Close={prev_close_str}")

    ib = IB()

    try:
        # Client ID 1 is standard for primary monitoring connections
        ib.connect("127.0.0.1", 4002, clientId=1)
        logger.info("Successfully connected to IB Gateway.")
    except Exception as e:
        logger.error(f"Failed to connect to IB Gateway: {e}")
        sys.exit(1)

    # Start the monitoring service
    monitor = monitor_market_open(ib, watch_targets)

    logger.info("Listening for Market Open (06:30 PST) and building candles (5m, 15m, 30m)...")

    try:
        while True:
            now = datetime.datetime.now()
            monitor.check_time_alerts(now.time())
            
            if monitor.alerted_30m:
                logger.info("⏰ All timeframes completed. Finalizing monitor.")
                break
            
            ib.sleep(5)

    except KeyboardInterrupt:
        logger.warning("🛑 Ctrl+C detected. Finalizing early...")
        if not monitor.alerted_5m: monitor._alert_timeframe("5m")
        elif not monitor.alerted_15m: monitor._alert_timeframe("15m")
        elif not monitor.alerted_30m: monitor._alert_timeframe("30m")
    finally:
        if ib.isConnected():
            ib.disconnect()
            logger.info("🔌 Disconnected cleanly from IB Gateway. Goodbye!")

if __name__ == "__main__":
    main()
