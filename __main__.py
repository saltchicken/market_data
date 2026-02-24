import datetime
import time
import argparse
import logging
from ib_insync import IB

from config import StrategyConfig
from utils import setup_logging
from execution import ensure_connection, get_available_funds

from account import verify_paper_account, verify_cash_account
from data import get_sp500_symbols
from scanner import run_daily_buy_scan, monitor_open_positions


def parse_arguments():
    parser = argparse.ArgumentParser(description="Algorithmic Trading Bot")
    parser.add_argument(
        "--monitor-only",
        action="store_true",
        help="Skip the daily buy scan and only monitor open positions.",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    setup_logging()
    logging.info("Starting Paper Trading Bot...")

    if args.monitor_only:
        logging.info("‼️ RUNNING IN MONITOR-ONLY MODE. Buy scanning is disabled.")

    ib = IB()
    config = StrategyConfig()

    scan_state = {"date": None, "all_symbols": [], "remaining_symbols": []}

    try:
        while True:
            try:
                ensure_connection(ib, config)

                config.account_capital = get_available_funds(ib)

                if not args.monitor_only:
                    now = datetime.datetime.now()

                    if scan_state["date"] != now.date():
                        logging.info(
                            "New day detected. Fetching fresh symbols for daily scan..."
                        )
                        scan_state["date"] = now.date()

                        scan_state["all_symbols"] = get_sp500_symbols()
                        scan_state["remaining_symbols"] = list(
                            scan_state["all_symbols"]
                        )

                    # If the remaining queue empties out, instantly refill it from the cache!
                    if (
                        not scan_state["remaining_symbols"]
                        and scan_state["all_symbols"]
                    ):
                        logging.info(
                            "‼️ Scan complete! Restarting S&P 500 loop from the beginning..."
                        )
                        scan_state["remaining_symbols"] = list(
                            scan_state["all_symbols"]
                        )

                # Priority 1 - ALWAYS monitor open positions first to ensure quick exits
                monitor_open_positions(ib, config)

                # Priority 2 - Process a small chunk of new buy signals
                if not args.monitor_only and scan_state["remaining_symbols"]:
                    run_daily_buy_scan(ib, config, scan_state, chunk_size=5)

                    # Small delay between chunks to let the IBKR data farm breathe
                    ib.sleep(5)
                else:

                    # since the remaining_symbols list will instantly refill otherwise.
                    logging.info("Monitor-only mode active. Sleeping 5 mins...")
                    ib.sleep(60 * 5)

            except Exception as e:
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
