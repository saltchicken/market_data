import os
import sys
import datetime
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from ib_insync import IB, Stock, util


def get_watchlist_from_db(db_url: str) -> list:
    """Fetch the active watchlist tickers from the PostgreSQL database."""
    if not db_url:
        print("Error: DB_URL is not set in the environment variables.", file=sys.stderr)
        return []

    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Added ORDER BY updated_at DESC so the most recently added/updated 
            # tickers are prioritized if the count exceeds IBKR's 50 limit.
            query = text("""
                SELECT ticker 
                FROM watchlist 
                ORDER BY updated_at DESC 
                LIMIT 50;
            """)
            result = conn.execute(query)
            tickers = [row[0] for row in result]
        return tickers
    except Exception as e:
        print(f"Error fetching watchlist from database: {e}", file=sys.stderr)
        return []


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

        # Here you can add your custom indicator calculations or alert triggers
        print(f"[{symbol}] New 5m candle closed. Latest 30m state:")
        print(df_30m.tail(1))
        print("-" * 40)


def subscribe_historical_bars(ib: IB, symbols: list) -> dict:
    """Qualify contracts and stagger the historical data requests."""
    contracts = [Stock(symbol, "SMART", "USD") for symbol in symbols]
    ib.qualifyContracts(*contracts)

    live_bars = {}
    print("\nInitializing historical data requests for PREMARKET...")

    for contract in contracts:
        # Request a 15-minute historical seed to initialize the DataFrame, then switch to live
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
        bars.updateEvent += on_bar_update

        # Store in our dictionary to keep the reference alive
        live_bars[contract.symbol] = bars

        print(f"Subscribed to {contract.symbol}")

        # Stagger requests by 2 seconds to avoid IBKR pacing violations
        ib.sleep(2)

    return live_bars


def main():
    # 1. Load environment variables and fetch watchlist
    load_dotenv()
    db_url = os.getenv("DB_URL")

    watch_list = get_watchlist_from_db(db_url)

    if not watch_list:
        print("Watchlist is empty or could not be loaded from the database. Exiting.")
        sys.exit(1)

    print(f"Loaded {len(watch_list)} active tickers from the database:")
    print(f"  -> {', '.join(watch_list)}\n")

    # Optional guardrail: Warn if approaching the 50 simultaneous request limit
    if len(watch_list) > 45:
        print("⚠️ WARNING: Watchlist contains more than 45 tickers.", file=sys.stderr)
        print(
            "You are close to IBKR's hard limit of 50 simultaneous historical requests.",
            file=sys.stderr,
        )

    # 2. Initialize the IB connection
    ib = IB()

    # Connect to IB Gateway running on your local machine (Port 4002 for Paper, 4001 for Live)
    try:
        ib.connect("127.0.0.1", 4002, clientId=1)
    except Exception as e:
        print(f"Failed to connect to IB Gateway: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. Subscribe to staggered historical bars
    live_bars = subscribe_historical_bars(ib, watch_list)

    print("\nAll contracts subscribed. Listening for 5-minute candle closes...")

    # 4. Define end-of-day stop time (e.g., 1:05 PM PDT / 4:05 PM EDT)
    stop_hour = 13
    stop_minute = 5

    # 5. Time-aware event loop
    try:
        while True:
            # Sleep allows background events to fire while preventing CPU pegging
            ib.sleep(60)

            now = datetime.datetime.now()

            # Check if we have reached or passed the stop time
            if now.hour >= stop_hour and now.minute >= stop_minute:
                print(f"\n⏰ Reached {stop_hour}:{stop_minute:02d}. Market is closed.")
                break

    except KeyboardInterrupt:
        print("\n🛑 Ctrl+C detected. Stopping data stream...")
    finally:
        if ib.isConnected():
            ib.disconnect()
            print("🔌 Disconnected cleanly from IB Gateway. Goodbye!")


if __name__ == "__main__":
    main()
