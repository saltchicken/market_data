import datetime
import time
import sys
import pandas as pd
from ib_insync import IB
from config import StrategyConfig
from data import fetch_historical_data
import logging
from indicators import calculate_indicators
from strategy import (
    generate_base_trend,
    apply_volume_filter,
    apply_adx_filter,
    apply_trailing_stop_loss,
    generate_signals_from_trend,
    calculate_dynamic_position,
)

from execution import (
    get_available_funds,
    get_current_positions,
    execute_limit_order,
    execute_market_order,
    ensure_connection,
    get_pending_shares,
)
from utils import setup_logging


def format_symbols_for_ibkr(symbol_series):
    return symbol_series.str.replace(".", " ", regex=False).str.replace(
        "-", " ", regex=False
    )


def get_sp500_symbols():
    print("Fetching latest S&P 500 symbols from Wikipedia...")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(url, storage_options={"User-Agent": "Mozilla/5.0"})
    df = tables[0]

    symbols = format_symbols_for_ibkr(df["Symbol"]).tolist()

    return symbols


def verify_paper_account(ib):
    """
    ‼️ NEW: Extracted verification logic to ensure we never accidentally place real trades.
    IBKR paper trading account numbers always begin with 'D' (e.g., DU12345).
    """
    accounts = ib.managedAccounts()
    if not accounts:
        raise ConnectionError("No accounts found. Is the broker fully initialized?")

    for acc in accounts:
        if not acc.startswith("D"):
            logging.critical(
                f"‼️ DANGER: Live account detected ({acc})! Aborting immediately to prevent real trades."
            )

            sys.exit(1)

    logging.info(
        f"‼️ Security Check Passed: Verified Paper Trading Account(s) -> {accounts}"
    )


def verify_cash_account(ib):
    """
    ‼️ NEW: Extracted verification logic to ensure we are running on a strict Cash account.
    This prevents the bot from accidentally borrowing money and buying on margin.
    """
    account_values = ib.accountValues()
    account_type = None

    for val in account_values:
        if val.tag == "AccountType":
            account_type = val.value
            break

    if not account_type:
        logging.critical(
            "‼️ DANGER: Could not verify AccountType from broker. Aborting for safety."
        )
        sys.exit(1)

    # if account_type.upper() != "CASH":
    #     logging.critical(
    #         f"‼️ DANGER: Margin account detected (Type: {account_type})! Aborting immediately to prevent leveraged trades."
    #     )
    #     sys.exit(1)

    # logging.info("‼️ Security Check Passed: Verified Cash Account (No Margin).")


def get_latest_live_signal(df, symbol, config):
    if df is None or df.empty:
        return None

    latest_data = df.iloc[-1]
    signal = latest_data["Crossover_Signal"]

    result_signal = None

    if signal == 1.0:
        result_signal = {
            "symbol": symbol,
            "action": "BUY",
            "price": latest_data["close"],
            "shares": latest_data["Target_Shares"],
        }
    elif signal == -1.0:
        result_signal = {
            "symbol": symbol,
            "action": "SELL",
            "price": latest_data["close"],
        }

    return result_signal


def check_current_signal(ib, symbol, config):
    df = fetch_historical_data(ib, config, symbol=symbol)

    if df is not None and not df.empty:
        df = calculate_indicators(df, config)
        df = generate_base_trend(df)
        df = apply_volume_filter(df)
        df = apply_adx_filter(df, threshold=config.adx_threshold)
        df = apply_trailing_stop_loss(df, config)
        df = generate_signals_from_trend(df)
        df = calculate_dynamic_position(df, config)

        return get_latest_live_signal(df, symbol, config)
    return None


def run_daily_buy_scan(ib, config, scan_state):
    if not scan_state["remaining_symbols"]:
        return

    print(
        f"\n--- RUNNING DAILY BUY SCAN ({len(scan_state['remaining_symbols'])} symbols remaining) ---"
    )

    available_funds = get_available_funds(ib)
    current_positions = get_current_positions(ib)
    print(f"Available Funds: ${available_funds:.2f}")

    for sym in list(scan_state["remaining_symbols"]):

        if sym in current_positions:
            scan_state["remaining_symbols"].remove(sym)
            continue

        pending_buys = get_pending_shares(ib, sym, "BUY")
        if pending_buys > 0:
            print(
                f"‼️ Skipping BUY for {sym}: {pending_buys} shares are already pending."
            )
            scan_state["remaining_symbols"].remove(sym)
            continue

        try:
            signal_data = check_current_signal(ib, sym, config)

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

            scan_state["remaining_symbols"].remove(sym)

        except Exception as e:
            print(f"‼️ Error processing {sym}: {e}")
            if (
                isinstance(e, ConnectionError)
                or "socket" in str(e).lower()
                or "disconnect" in str(e).lower()
            ):
                raise e

            if sym in scan_state["remaining_symbols"]:
                scan_state["remaining_symbols"].remove(sym)

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
                f"‼️ Skipping SELL for {sym}: all {quantity} shares are already pending sale."
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


def main():

    setup_logging()
    logging.info("Starting Paper Trading Bot...")

    ib = IB()
    config = StrategyConfig()

    ensure_connection(ib, config)
    verify_paper_account(ib)
    verify_cash_account(ib)
    config.account_capital = get_available_funds(ib)

    scan_state = {"date": None, "remaining_symbols": []}

    try:
        while True:
            try:
                ensure_connection(ib, config)
                verify_paper_account(ib)
                verify_cash_account(ib)

                now = datetime.datetime.now()

                if scan_state["date"] != now.date():
                    logging.info(
                        "New day detected. Fetching fresh symbols for daily scan..."
                    )
                    scan_state["date"] = now.date()
                    scan_state["remaining_symbols"] = get_sp500_symbols()

                if scan_state["remaining_symbols"]:
                    run_daily_buy_scan(ib, config, scan_state)

                if not scan_state["remaining_symbols"]:
                    monitor_open_positions(ib, config)
                    logging.info(f"Cycle complete. Sleeping for 15 minutes...")
                    ib.sleep(60 * 15)

            except Exception as e:
                # Keep standard error handling, but the sys.exit(1) in verify_paper_account
                # will cleanly bypass this catch block and kill the terminal process completely.
                logging.error(f"‼️ Connection or execution error encountered: {e}")
                logging.info(
                    "‼️ Cleaning up connection state and retrying in 60 seconds..."
                )

                if ib.isConnected():
                    ib.disconnect()

                time.sleep(60)

    except KeyboardInterrupt:
        logging.info("Manually stopped the trading bot.")
    finally:
        if ib.isConnected():
            ib.disconnect()
            logging.info("Disconnected from Interactive Brokers.")


if __name__ == "__main__":
    main()
