import os
import sys
import datetime
import logging
import json
import urllib.request
from logging.handlers import RotatingFileHandler
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from ib_insync import IB, Stock, util

# Initialize a module-level logger
logger = logging.getLogger("ibkr_alerts")

def setup_logging():
    """Configures logging to both console and rotating files."""
    logger.setLevel(logging.INFO)
    
    # Formatter for the logs
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s', 
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # 2. File Handler (General Logs) - Max 5MB per file, keep 3 backups
    file_handler = RotatingFileHandler(
        'ibkr_alerts.log', maxBytes=5*1024*1024, backupCount=3
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # 3. File Handler (Alerts Only)
    alert_file_handler = RotatingFileHandler(
        'ibkr_alerts_triggered.log', maxBytes=5*1024*1024, backupCount=3
    )
    alert_file_handler.setLevel(logging.WARNING) # Alerts will be logged as WARNING or higher
    alert_file_handler.setFormatter(formatter)

    # Clear existing handlers to prevent duplicates if called consecutively
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(alert_file_handler)

    # Silence overly verbose ib_insync debug logs
    logging.getLogger('ib_insync').setLevel(logging.ERROR)


def trigger_alert(title: str, message: str):
    """
    Logs the alert and sends push notifications if webhooks are configured.
    Set DISCORD_WEBHOOK_URL or TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID in your .env
    """
    full_msg = f"{title}: {message}"
    
    # Log as WARNING so it routes to the console, main log, AND the alerts-only log file
    logger.warning(full_msg)

    # --- Discord Integration ---
    discord_url = os.getenv("DISCORD_WEBHOOK_URL")
    if discord_url:
        try:
            req = urllib.request.Request(discord_url, method="POST")
            req.add_header('Content-Type', 'application/json')
            req.add_header('User-Agent', 'Mozilla/5.0')
            data = json.dumps({"content": full_msg}).encode('utf-8')
            urllib.request.urlopen(req, data=data, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")

    # --- Telegram Integration ---
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if telegram_token and telegram_chat_id:
        try:
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            req = urllib.request.Request(url, method="POST")
            req.add_header('Content-Type', 'application/json')
            data = json.dumps({"chat_id": telegram_chat_id, "text": full_msg}).encode('utf-8')
            urllib.request.urlopen(req, data=data, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")


def get_watchlist_targets_from_db(db_url: str) -> dict:
    """Fetch active watchlist tickers AND their targets from the PostgreSQL database."""
    if not db_url:
        logger.error("DB_URL is not set in the environment variables.")
        return {}

    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            query = text("""
                SELECT ticker, target_buy, target_sell, target_volume 
                FROM watchlist 
                ORDER BY updated_at DESC 
                LIMIT 50;
            """)
            result = conn.execute(query)
            
            # Map results to a dictionary: { 'AAPL': {'target_buy': 150, 'target_volume': 50000}, ... }
            targets = {}
            for row in result:
                targets[row[0]] = {
                    'target_buy': row[1],
                    'target_sell': row[2],
                    'target_volume': row[3]
                }
        return targets
    except Exception as e:
        logger.error(f"Error fetching watchlist from database: {e}")
        return {}


def create_bar_handler(targets_dict: dict):
    """Factory function to create a closure that holds the target dictionaries."""
    
    def on_bar_update(bars, hasNewBar):
        """Callback function triggered when a new bar updates or closes."""
        # ONLY run the heavy Pandas logic if a 5-minute candle has officially closed
        if hasNewBar:
            symbol = bars.contract.symbol

            # Convert the ib_insync bars to a Pandas DataFrame
            df = util.df(bars)
            df.set_index("date", inplace=True)

            # Resample to 30 minutes
            ohlcv_dict = {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
            df_30m = df.resample("30min").agg(ohlcv_dict).dropna()
            
            if df_30m.empty:
                return

            latest_30m = df_30m.iloc[-1]
            latest_volume = latest_30m['volume']
            latest_close = latest_30m['close']
            
            # Fetch specific targets for this symbol
            symbol_targets = targets_dict.get(symbol, {})
            t_vol = symbol_targets.get('target_volume')
            t_buy = symbol_targets.get('target_buy')
            t_sell = symbol_targets.get('target_sell')

            # Standard Info logging for regular 30m closes
            logger.info(f"[{symbol}] 30m Closed | Close: ${latest_close:.2f} | Vol: {latest_volume:,.0f}")

            # --- ALERT LOGIC ---
            if t_vol and latest_volume >= t_vol:
                trigger_alert("🚨 VOLUME SURGE", f"{symbol} volume ({latest_volume:,.0f}) exceeded target ({t_vol:,.0f})!")
                
            if t_buy and latest_close <= t_buy:
                trigger_alert("💸 BUY TARGET REACHED", f"{symbol} dropped to ${latest_close:.2f} (Target: ${t_buy:.2f})!")

            if t_sell and latest_close >= t_sell:
                trigger_alert("💰 SELL TARGET REACHED", f"{symbol} climbed to ${latest_close:.2f} (Target: ${t_sell:.2f})!")

    return on_bar_update


def subscribe_historical_bars(ib: IB, targets_dict: dict) -> dict:
    """Qualify contracts and stagger the historical data requests."""
    symbols = list(targets_dict.keys())
    contracts = [Stock(symbol, "SMART", "USD") for symbol in symbols]
    ib.qualifyContracts(*contracts)

    live_bars = {}
    logger.info("Initializing historical data requests for PREMARKET...")
    
    # Generate our specific callback handler injected with the targets
    bar_handler = create_bar_handler(targets_dict)

    for contract in contracts:
        bars = ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr="900 S",
            barSizeSetting="5 mins",
            whatToShow="TRADES",
            useRTH=False,  # CRITICAL: False allows premarket/after-hours data
            keepUpToDate=True,
        )

        # Attach the event handler
        bars.updateEvent += bar_handler

        # Store in our dictionary to keep the reference alive
        live_bars[contract.symbol] = bars

        logger.info(f"Subscribed to {contract.symbol}")
        ib.sleep(2) # Stagger requests

    return live_bars


def main():
    setup_logging()
    logger.info("Starting IBKR Alerts Module...")

    load_dotenv()
    db_url = os.getenv("DB_URL")

    # Fetch the rich watchlist including targets
    watch_targets = get_watchlist_targets_from_db(db_url)

    if not watch_targets:
        logger.error("Watchlist is empty or could not be loaded from the database. Exiting.")
        sys.exit(1)

    logger.info(f"Loaded {len(watch_targets)} active tickers and targets from the database:")
    for ticker, data in watch_targets.items():
        vol_str = f"{data['target_volume']:,.0f}" if data['target_volume'] else "None"
        buy_str = f"${data['target_buy']:.2f}" if data['target_buy'] else "None"
        sell_str = f"${data['target_sell']:.2f}" if data['target_sell'] else "None"
        logger.info(f"  -> {ticker}: Vol={vol_str} | Buy={buy_str} | Sell={sell_str}")

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

    logger.info("All contracts subscribed. Listening for 5-minute candle closes...")

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
