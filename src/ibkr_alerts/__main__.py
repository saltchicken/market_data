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

WATCH_LIST = {
    "AAPL": {"breakout_price": 175.50, "volume_surge": 5000000},
    "MSFT": {"breakout_price": 410.00, "volume_surge": 3000000},
    "INVALID": {"breakout_price": 180.00, "volume_surge": 10000000}
}


def setup_contracts(ib: IB, symbols: list) -> list:
    """Create and qualify contracts for the given symbols."""
    contracts = [Stock(symbol, "SMART", "USD") for symbol in symbols]
    return ib.qualifyContracts(*contracts)


def subscribe_market_data(ib: IB, contracts: list):
    """Request real-time streaming data for qualified contracts."""
    # 3 = Delayed data (or whatever tier applies based on subscriptions)
    ib.reqMarketDataType(3)
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
    # 1. Initialize the IB connection
    ib = IB()

    # Connect to IB Gateway running on your local machine on port 4002 for Paper Trading Account.
    ib.connect("127.0.0.1", 4002, clientId=1)

    # 2. Setup and qualify contracts
    symbols = list(WATCH_LIST.keys())
    contracts = setup_contracts(ib, symbols)

    # 3. Request real-time streaming data
    subscribe_market_data(ib, contracts)

    print("Waiting for data stream to stabilize...")
    ib.sleep(2)

    # 4. Bind the extracted event handler
    ib.pendingTickersEvent += process_pending_tickers

    print("Streaming live market data... Press Ctrl+C to stop.")

    # 5. Run the event loop safely
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
