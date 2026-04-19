import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from ib_insync import IB, Stock

TICK_TYPE_MAP = {
    # --- LIVE DATA ---
    0: "Bid Size",
    1: "Live Bid",
    2: "Live Ask",
    3: "Ask Size",
    4: "Live Last Trade",
    5: "Live Last Size",
    6: "Live High",
    7: "Live Low",
    8: "Live Volume",
    9: "Live Close",
    14: "Live Open",
    # --- DELAYED DATA ---
    66: "Delayed Bid",
    67: "Delayed Ask",
    68: "Delayed Last Trade",
    69: "Delayed Last Size",
    72: "Delayed High",
    73: "Delayed Low",
    74: "Delayed Volume",
    75: "Delayed Close",
    76: "Delayed Open",
    # --- OPTIONS & OTHER ---
    24: "Option Implied Vol",
    45: "Last Timestamp",
    84: "Last Exchange",
    86: "Futures Open Interest",
}


def get_watchlist_from_db(db_url: str) -> list:
    """Fetch the active watchlist tickers from the PostgreSQL database."""
    if not db_url:
        print("Error: DB_URL is not set in the environment variables.", file=sys.stderr)
        return []

    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            query = text("SELECT ticker FROM watchlist WHERE is_active = TRUE;")
            result = conn.execute(query)
            tickers = [row[0] for row in result]
        return tickers
    except Exception as e:
        print(f"Error fetching watchlist from database: {e}", file=sys.stderr)
        return []


def setup_contracts(ib: IB, symbols: list) -> list:
    """Create and qualify contracts for the given symbols."""
    contracts = [Stock(symbol, "SMART", "USD") for symbol in symbols]
    return ib.qualifyContracts(*contracts)


def subscribe_market_data(ib: IB, contracts: list):
    """Request real-time streaming data for qualified contracts."""
    for contract in contracts:
        ib.reqMktData(contract, "", False, False)


def process_pending_tickers(tickers):
    """Callback function to process incoming ticker data updates."""
    for t in tickers:
        if not t.ticks:
            print(f"[{t.contract.symbol}] Received empty tick data. Skipping...")
            continue

        print(f"\n--- 📡 New Data Update for {t.contract.symbol} ---")
        processed_ticks = []

        for tick in t.ticks:
            tick_name = TICK_TYPE_MAP.get(
                tick.tickType, f"Unknown Tick ({tick.tickType})"
            )
            processed_ticks.append((tick.tickType, tick_name, tick.price, tick.size))

        # Sort by tick type ID for consistent display
        processed_ticks.sort(key=lambda x: x[0])

        for tick_id, name, price, size in processed_ticks:
            print(f"[{tick_id:02d}] {name:<18} | Price: {price:<8} | Size: {size}")


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

    # 2. Initialize the IB connection
    ib = IB()

    # Connect to IB Gateway running on your local machine on port 4002 for Paper Trading Account.
    try:
        ib.connect("127.0.0.1", 4002, clientId=1)
    except Exception as e:
        print(f"Failed to connect to IB Gateway: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. Setup and qualify contracts
    contracts = setup_contracts(ib, watch_list)

    if not contracts:
        print("Could not qualify any contracts. Exiting.")
        ib.disconnect()
        sys.exit(1)

    # 4. Request real-time streaming data
    subscribe_market_data(ib, contracts)

    print("Waiting for data stream to stabilize...")
    ib.sleep(2)

    # 5. Bind the extracted event handler
    ib.pendingTickersEvent += process_pending_tickers

    print("Streaming live market data... Press Ctrl+C to stop.")

    # 6. Run the event loop safely
    try:
        ib.run()
    except KeyboardInterrupt:
        print("\n🛑 Ctrl+C detected. Stopping data stream...")
    finally:
        if ib.isConnected():
            ib.disconnect()
            print("🔌 Disconnected cleanly from IB Gateway. Goodbye!")


if __name__ == "__main__":
    main()
