import os
import sys
import time
import gc
import argparse
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from polygon import RESTClient
from sqlalchemy import create_engine

from .database import init_database
from .fetcher import fetch_and_upload
from .indicators import run_python_indicator_pipeline

def main():
    parser = argparse.ArgumentParser(description="Market Data Fetcher and Indicator Calculator")
    
    # Create a mutually exclusive group so we can't accidentally reset AND recalc
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--reset", 
        action="store_true", 
        help="Wipe the database, re-download 2 years of data, and bulk calculate indicators."
    )
    group.add_argument(
        "--recalc", 
        action="store_true", 
        help="Re-calculate all indicators from existing raw data without fetching new data."
    )
    
    args = parser.parse_args()

    load_dotenv()
    API_KEY = os.getenv("POLYGON_API_KEY")
    DB_URL = os.getenv("DB_URL")

    if not API_KEY or not DB_URL:
        print("Error: Missing env variables. Ensure POLYGON_API_KEY and DB_URL are set.")
        sys.exit(1)

    # --- Initialize global connections ONCE ---
    engine = create_engine(DB_URL)
    client = RESTClient(API_KEY)

    if args.reset:
        print("\n=== STARTING 2-YEAR DATABASE RESET ===")
        init_database(DB_URL)

        end_date = datetime.today()
        start_date = end_date - timedelta(days=730)
        dates_to_fetch = pd.bdate_range(start=start_date, end=end_date)

        print(f"\n[PHASE 1] Fetching {len(dates_to_fetch)} days of raw market data...")
        for date_obj in dates_to_fetch:
            target_date = date_obj.strftime("%Y-%m-%d")
            print(f"\n--- Processing Raw Data: {target_date} ---")
            
            # Pass the engine and client into the function
            fetch_and_upload(target_date, engine, client)
            
            print("Sleeping for 13 seconds to avoid rate limits...")
            time.sleep(13)
            
            # Force memory cleanup after each day to prevent RAM bloat
            gc.collect()

        print("\n[PHASE 2] Bulk calculating all indicators...")
        run_python_indicator_pipeline(engine, target_date=None)

        print("\n=== RESET COMPLETE ===")

    elif args.recalc:
        print("\n=== RECALCULATING ALL INDICATORS FROM EXISTING RAW DATA ===")
        # Because target_date is None, this will automatically truncate the
        # daily_indicators table before bulk-inserting the new calculations.
        run_python_indicator_pipeline(engine, target_date=None)
        print("\n=== RECALCULATION COMPLETE ===")

    else:
        # Standard Daily Run
        TARGET_DATE = datetime.today().strftime("%Y-%m-%d")
        print(f"\n=== RUNNING DAILY UPDATE FOR {TARGET_DATE} ===")

        data_fetched = fetch_and_upload(TARGET_DATE, engine, client)
        
        if not data_fetched:
            print(f"Halting process: No market data was found for {TARGET_DATE}. Skipping indicator calculation.")
            sys.exit(1)

        run_python_indicator_pipeline(engine, target_date=TARGET_DATE)


if __name__ == "__main__":
    main()
