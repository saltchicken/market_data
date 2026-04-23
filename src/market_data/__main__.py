import os
import sys
import time
import gc
import logging
import argparse
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from polygon import RESTClient
from sqlalchemy import create_engine

from core.log_config import setup_logging
from .database import init_database
from .fetcher import fetch_and_upload
from .indicators import run_python_indicator_pipeline

logger = logging.getLogger("market_data")


def main():
    setup_logging("market_data")

    parser = argparse.ArgumentParser(
        description="Market Data Fetcher and Indicator Calculator"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--reset", action="store_true", help="Wipe and rebuild 2 years of data"
    )
    group.add_argument(
        "--recalc", action="store_true", help="Re-calculate all indicators"
    )
    args = parser.parse_args()

    load_dotenv()
    API_KEY = os.getenv("POLYGON_API_KEY")
    DB_URL = os.getenv("DB_URL")

    if not API_KEY or not DB_URL:
        logger.error(
            "Missing env variables. Ensure POLYGON_API_KEY and DB_URL are set."
        )
        sys.exit(1)

    engine = create_engine(DB_URL)
    client = RESTClient(API_KEY)

    if args.reset:
        logger.info("=== STARTING 2-YEAR DATABASE RESET ===")
        init_database(DB_URL)

        end_date = datetime.today()
        start_date = end_date - timedelta(days=730)
        dates_to_fetch = pd.bdate_range(start=start_date, end=end_date)

        logger.info(
            f"[PHASE 1] Fetching {len(dates_to_fetch)} days of raw market data..."
        )
        for date_obj in dates_to_fetch:
            target_date = date_obj.strftime("%Y-%m-%d")
            logger.info(f"--- Processing Raw Data: {target_date} ---")

            fetch_and_upload(target_date, engine, client)

            logger.info("Sleeping for 13 seconds to avoid rate limits...")
            time.sleep(13)
            gc.collect()

        logger.info("[PHASE 2] Bulk calculating all indicators...")
        run_python_indicator_pipeline(engine, target_date=None)

        logger.info("=== RESET COMPLETE ===")

    elif args.recalc:
        logger.info("=== RECALCULATING ALL INDICATORS FROM EXISTING RAW DATA ===")
        run_python_indicator_pipeline(engine, target_date=None)
        logger.info("=== RECALCULATION COMPLETE ===")

    else:
        TARGET_DATE = datetime.today().strftime("%Y-%m-%d")
        logger.info(f"=== RUNNING DAILY UPDATE FOR {TARGET_DATE} ===")

        data_fetched = fetch_and_upload(TARGET_DATE, engine, client)

        if not data_fetched:
            logger.warning(f"Halting process: No market data found for {TARGET_DATE}.")
            sys.exit(1)

        run_python_indicator_pipeline(engine, target_date=TARGET_DATE)


if __name__ == "__main__":
    main()
