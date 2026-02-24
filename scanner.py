# This keeps __main__.py free of granular loop implementations.

from strategy import check_current_signal
from execution import (
    get_available_funds,
    get_current_positions,
    get_pending_shares,
    execute_limit_order,
    execute_market_order,
)


def run_daily_buy_scan(ib, config, scan_state, chunk_size=5):
    if not scan_state["remaining_symbols"]:
        return

    chunk = scan_state["remaining_symbols"][:chunk_size]
    scan_state["remaining_symbols"] = scan_state["remaining_symbols"][chunk_size:]

    print(
        f"\n--- SCANNING BUY CHUNK ({len(chunk)} symbols) | {len(scan_state['remaining_symbols'])} left today ---"
    )

    available_funds = get_available_funds(ib)
    current_positions = get_current_positions(ib)
    print(f"Available Funds: ${available_funds:.2f}")

    for sym in chunk:
        if sym in current_positions:
            continue

        pending_buys = get_pending_shares(ib, sym, "BUY")
        if pending_buys > 0:
            print(f"Skipping BUY for {sym}: {pending_buys} shares are already pending.")
            continue

        try:
            signal_data = check_current_signal(ib, sym, config)

            if signal_data:
                print(f"SCANNED: {sym} | Current Price: ${signal_data['price']:.2f}")

            if signal_data and signal_data["action"] == "BUY":
                estimated_cost = signal_data["shares"] * signal_data["price"]

                if available_funds >= estimated_cost:
                    print(f"🚨 EXECUTING BUY: {sym}")
                    execute_limit_order(
                        ib, sym, "BUY", signal_data["shares"], signal_data["price"]
                    )
                    available_funds -= estimated_cost
                else:
                    print(
                        f"⚠️ INSUFFICIENT FUNDS to buy {sym}. Cost: ${estimated_cost:.2f}, Available: ${available_funds:.2f}"
                    )

        except Exception as e:
            print(f"‼️ Error processing {sym}: {e}")
            if (
                isinstance(e, ConnectionError)
                or "socket" in str(e).lower()
                or "disconnect" in str(e).lower()
            ):

                scan_state["remaining_symbols"].insert(0, sym)
                raise e

        ib.sleep(2)  # Prevent API pacing errors


def monitor_open_positions(ib, config):
    print("\n--- MONITORING OPEN POSITIONS ---")
    current_positions = get_current_positions(ib)

    if not current_positions:
        print("No open positions to monitor.")
        return

    for sym, quantity in current_positions.items():
        print(f"Checking {sym} (Holding {quantity} shares)...")

        pending_sells = get_pending_shares(ib, sym, "SELL")
        shares_to_sell = quantity - pending_sells

        if shares_to_sell <= 0:
            print(
                f"Skipping SELL for {sym}: all {quantity} shares are already pending sale."
            )
            continue

        try:
            signal_data = check_current_signal(ib, sym, config)

            if signal_data and signal_data["action"] == "SELL":
                print(f"🚨 EXECUTING SELL: {sym}")
                execute_market_order(ib, sym, "SELL", shares_to_sell)

        except Exception as e:
            print(f"Error monitoring {sym}: {e}")

        ib.sleep(2)
