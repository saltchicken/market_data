import os
import sys
import datetime
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from ib_insync import IB, Stock, util


def get_watchlist_targets_from_db(db_url: str) -> dict:
    """Fetch active watchlist tickers AND their targets from the PostgreSQL database."""
    if not db_url:
        print("Error: DB_URL is not set in the environment variables.", file=sys.stderr)
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
        print(f"Error fetching watchlist from database: {e}", file=sys.stderr)
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

            print(f"[{symbol}] 30m Closed | Close: ${latest_close:.2f} | Vol: {latest_volume:,.0f}")

            # --- ALERT LOGIC ---
            if t_vol and latest_volume >= t_vol:
                print(f"  🚨 VOLUME SURGE ALERT: {symbol} volume ({latest_volume:,.0f}) exceeded target ({t_vol:,.0f})!")
                
            if t_buy and latest_close <= t_buy:
                print(f"  💸 BUY TARGET REACHED: {symbol} dropped to ${latest_close:.2f} (Target: ${t_buy:.2f})!")

    return on_bar_update


def subscribe_historical_bars(ib: IB, targets_dict: dict) -> dict:
    """Qualify contracts and stagger the historical data requests."""
    symbols = list(targets_dict.keys())
    contracts = [Stock(symbol, "SMART", "USD") for symbol in symbols]
    ib.qualifyContracts(*contracts)

    live_bars = {}
    print("\nInitializing historical data requests for PREMARKET...")
    
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

        print(f"Subscribed to {contract.symbol}")
        ib.sleep(2) # Stagger requests

    return live_bars


def main():
    load_dotenv()
    db_url = os.getenv("DB_URL")

    # Fetch the rich watchlist including targets
    watch_targets = get_watchlist_targets_from_db(db_url)

    if not watch_targets:
        print("Watchlist is empty or could not be loaded from the database. Exiting.")
        sys.exit(1)

    print(f"Loaded {len(watch_targets)} active tickers and targets from the database:\n")
    for ticker, data in watch_targets.items():
        vol_str = f"{data['target_volume']:,.0f}" if data['target_volume'] else "None"
        print(f"  -> {ticker}: Vol Target = {vol_str}")

    if len(watch_targets) > 45:
        print("\n⚠️ WARNING: You are close to IBKR's hard limit of 50 simultaneous historical requests.", file=sys.stderr)

    ib = IB()

    try:
        ib.connect("127.0.0.1", 4002, clientId=1)
    except Exception as e:
        print(f"Failed to connect to IB Gateway: {e}", file=sys.stderr)
        sys.exit(1)

    # Pass the targets directly into the subscription manager
    live_bars = subscribe_historical_bars(ib, watch_targets)

    print("\nAll contracts subscribed. Listening for 5-minute candle closes...")

    stop_hour = 13
    stop_minute = 5

    try:
        while True:
            ib.sleep(60)
            now = datetime.datetime.now()

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
