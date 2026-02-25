import datetime
import time
import logging
from zoneinfo import ZoneInfo
import pandas_market_calendars as mcal

from ib_insync import IB
from config import StrategyConfig
from utils import setup_logging, create_error_handler
from execution import (
    ensure_connection,
    get_available_funds,
    cancel_all_open_orders,
    get_net_liquidation_value,
)
from data import get_sp500_symbols, get_all_us_symbols
from scanner import run_daily_buy_scan, monitor_open_positions


def _is_market_holiday(target_date):
    """
    Extracted check to verify if the stock market is officially closed.
    """
    nyse = mcal.get_calendar("NYSE")
    schedule = nyse.schedule(start_date=target_date, end_date=target_date)
    return schedule.empty


def _is_market_open():
    """
    Extracted market hours validation.
    Converts current time to US/Eastern to handle Daylight Saving Time automatically,
    then checks if it's a weekday between 9:30 AM and 4:00 PM EST.
    """
    now_est = datetime.datetime.now(ZoneInfo("US/Eastern"))

    # 5 = Saturday, 6 = Sunday
    if now_est.weekday() >= 5:
        return False

    if _is_market_holiday(now_est.date()):
        return False

    market_open = datetime.time(9, 30)
    market_close = datetime.time(16, 0)

    return market_open <= now_est.time() <= market_close


def _wait_for_market_open(ib):
    """
    Extracted sleep logic to pause the bot while the market is closed.
    Returns True if the market is open, False if it is sleeping.
    """
    if not _is_market_open():
        logging.info("Market is currently closed. Sleeping for 60 seconds...")
        # Keep the connection alive but do nothing else
        ib.sleep(60)
        return False
    return True


def _is_approaching_close():
    """
    Extracted check for the final 5 minutes of the trading session.
    (3:55 PM to 4:00 PM EST)
    """
    now_est = datetime.datetime.now(ZoneInfo("US/Eastern"))
    market_close_warning = datetime.time(15, 55)
    market_close = datetime.time(16, 0)

    return market_close_warning <= now_est.time() < market_close


def _handle_daily_reset(scan_state, current_equity):
    """
    Checks if it's a new calendar day and fetches fresh symbols if so.
    """
    now_date = datetime.datetime.now().date()

    if scan_state["date"] != now_date:
        logging.info("‼️ NEW DAY DETECTED: Fetching fresh symbols for daily scan...")

        if current_equity:
            logging.info(f"📊 Daily Starting Equity: ${current_equity:,.2f}")

        scan_state["date"] = now_date

        # scan_state["all_symbols"] = get_sp500_symbols()
        scan_state["all_symbols"] = get_all_us_symbols()
        scan_state["remaining_symbols"] = list(scan_state["all_symbols"])

    if not scan_state["remaining_symbols"] and scan_state["all_symbols"]:
        logging.info("‼️ SCAN COMPLETE: Restarting loop from the beginning...")
        scan_state["remaining_symbols"] = list(scan_state["all_symbols"])


def _run_trading_cycle(ib, config, scan_state):
    """
    ‼️ NEW: Extracted the core trading cycle into its own function.
    Clearly separates Priority 1 (Risk Management) from Priority 2 (Scanning).
    """
    # Priority 1 - ALWAYS monitor open positions first to ensure quick exits
    monitor_open_positions(ib, config)

    # Priority 2 - Process a small chunk of new buy signals
    if scan_state["remaining_symbols"]:
        run_daily_buy_scan(ib, config, scan_state, chunk_size=20)

        # Small delay between chunks to let the IBKR data farm breathe
        ib.sleep(5)


def main():
    setup_logging()
    logging.info("Starting Paper Trading Bot...")

    ib = IB()
    ib.errorEvent += create_error_handler("bad_symbols.txt")

    config = StrategyConfig()
    scan_state = {"date": None, "all_symbols": [], "remaining_symbols": []}

    try:
        while True:
            try:
                ensure_connection(ib, config)

                # if not _wait_for_market_open(ib):
                #     continue

                if _is_approaching_close():
                    logging.info(
                        "Approaching market close. Halting scans and clearing open orders."
                    )
                    cancel_all_open_orders(ib)

                    # Sleep for exactly enough time to push us past the closing bell
                    # This prevents the bot from spamming the cancel function for 5 minutes
                    now_est = datetime.datetime.now(ZoneInfo("US/Eastern"))
                    target_close_time = datetime.datetime.combine(
                        now_est.date(),
                        datetime.time(16, 1),
                        tzinfo=ZoneInfo("US/Eastern"),
                    )

                    seconds_until_close = (target_close_time - now_est).total_seconds()

                    ib.sleep(max(10, seconds_until_close))
                    continue

                current_equity = get_net_liquidation_value(ib)
                if current_equity:
                    config.account_capital = current_equity

                _handle_daily_reset(scan_state, current_equity)
                _run_trading_cycle(ib, config, scan_state)

            except Exception as e:
                logging.error(f"‼️ Connection or execution error encountered: {e}")
                logging.info(
                    "Cleaning up connection state and retrying in 60 seconds..."
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
