import argparse
import os
import sys
import time
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from finvizfinance.screener.overview import Overview
from finvizfinance.screener.valuation import Valuation
from finvizfinance.screener.financial import Financial
from finvizfinance.screener.ownership import Ownership
from finvizfinance.screener.performance import Performance
from finvizfinance.screener.technical import Technical


def fetch_group_tickers(filters_dict: dict) -> pd.DataFrame:
    """
    Pulls the screener data for the specified filters across all tabs and merges them.

    Args:
        filters_dict (dict): A dictionary of filters (e.g., {'Sector': 'Technology'})

    Returns:
        pd.DataFrame: A DataFrame containing the combined screener data.
    """
    tabs = [
        ("Overview", Overview),
        ("Valuation", Valuation),
        ("Financial", Financial),
        ("Ownership", Ownership),
        ("Performance", Performance),
        ("Technical", Technical),
    ]

    merged_df = None

    for tab_name, screener_class in tabs:
        try:
            print(f"  -> Fetching {tab_name} tab...")
            screener = screener_class()

            # Only apply filters if they exist (allows fetching all tickers)
            if filters_dict:
                screener.set_filter(filters_dict=filters_dict)

            # Fetch the data. finvizfinance handles pagination automatically.
            df = screener.screener_view()

            if df.empty:
                continue

            if merged_df is None:
                merged_df = df
            else:
                # Only keep columns that aren't already in the merged dataframe, plus 'Ticker' to merge on
                new_cols = df.columns.difference(merged_df.columns).tolist()
                new_cols.append("Ticker")
                merged_df = pd.merge(merged_df, df[new_cols], on="Ticker", how="outer")

            # Add a delay to avoid Finviz's rate limits (HTTP 429 Too Many Requests)
            print(f"     (Waiting 3 seconds to respect rate limits...)")
            time.sleep(3)

        except Exception as e:
            print(f"Error fetching {tab_name} data from Finviz: {e}", file=sys.stderr)

    return merged_df if merged_df is not None else pd.DataFrame()


def clean_columns_for_db(df: pd.DataFrame) -> pd.DataFrame:
    """Formats column names to be strictly PostgreSQL-friendly and rounds numbers."""
    df_db = df.copy()

    # 1. General cleaning (lowercase, replace spaces/special chars)
    df_db.columns = (
        df_db.columns.str.lower()
        .str.replace(" ", "_")
        .str.replace("/", "_")
        .str.replace("%", "pct")
        .str.replace("(", "")
        .str.replace(")", "")
        .str.replace("-", "_")
    )

    # 2. Specific Renames (52w_high -> high_52w, etc.)
    # Note: The general cleaning above turns "52W High" into "52w_high"
    rename_map = {
        "52w_high": "high_52w",
        "52w_low": "low_52w"
    }
    df_db = df_db.rename(columns=rename_map)

    for col in df_db.columns:
        if df_db[col].dtype == 'object': # If Pandas thinks it's text
            if df_db[col].astype(str).str.contains('%').any():
                # Strip the '%' and convert to a float
                df_db[col] = df_db[col].astype(str).str.replace('%', '').astype(float)

    # 3. Numeric Rounding (The "I don't want to do this in SQL" fix)
    # This rounds all float/int columns to 2 decimal places automatically
    numeric_cols = df_db.select_dtypes(include=['number']).columns
    df_db[numeric_cols] = df_db[numeric_cols].round(2)

    return df_db


def main():
    # Load environment variables from .env file
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Find all tickers in a specific Finviz group (Sector, Industry, Country) or ALL tickers."
    )
    parser.add_argument(
        "--sector",
        type=str,
        help="Filter by Sector (e.g., 'Technology', 'Basic Materials')",
    )
    parser.add_argument(
        "--industry",
        type=str,
        help="Filter by Industry (e.g., 'Semiconductors', 'Gold')",
    )
    parser.add_argument(
        "--country", type=str, help="Filter by Country (e.g., 'USA', 'China')"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=True,
        help="Fetch ALL tickers (Warning: Takes a long time)",
    )

    # --- New Database & Export Arguments ---
    parser.add_argument(
        "--db-url",
        type=str,
        default=os.getenv("DB_URL"),
        help="PostgreSQL Connection URL. Defaults to DB_URL from .env file.",
    )
    parser.add_argument(
        "--db-table",
        type=str,
        default="finviz_screener",
        help="The name of the PostgreSQL table to insert the data into",
    )
    parser.add_argument(
        "--out-csv",
        type=str,
        help="Prefix/Path to save a daily CSV file (e.g., 'data/screener'). The date will be appended automatically.",
    )

    args = parser.parse_args()

    # Build the filter dictionary based on provided arguments
    filters = {}
    if args.sector:
        filters["Sector"] = args.sector
    if args.industry:
        filters["Industry"] = args.industry
    if args.country:
        filters["Country"] = args.country

    if not filters:
        print("Fetching ALL data tabs for ALL tickers (no filters applied)...")
    else:
        print(f"Fetching all data tabs for filters: {filters}...")

    df = fetch_group_tickers(filters)

    if df.empty:
        print("No tickers found for the specified filters, or an error occurred.")
        sys.exit(0)

    # --- Add timestamp for historical tracking ---
    current_date = datetime.today().strftime("%Y-%m-%d")
    df["Date"] = (
        pd.Timestamp.today().date()
    )

    # Extract just the ticker symbols
    tickers = df["Ticker"].tolist()
    print(f"\nFound {len(tickers)} tickers on {current_date}:\n")

    # --- CSV Export Logic ---
    if args.out_csv:
        csv_filename = f"{args.out_csv}_{current_date}.csv"
        df.to_csv(csv_filename, index=False)
        print(f"Successfully saved daily run to CSV: {csv_filename}")

    # --- Database Export Logic ---
    if args.db_url and args.db_table:
        print(f"\nExporting to PostgreSQL database table: '{args.db_table}'...")
        try:
            from sqlalchemy import create_engine

            # Create SQLAlchemy engine
            engine = create_engine(args.db_url)

            # Clean dataframe column names to be Postgres friendly (e.g. "Market Cap" -> "market_cap")
            df_db = clean_columns_for_db(df)

            # Changed from "replace" to "append" to keep historical data from previous days
            df_db.to_sql(args.db_table, engine, if_exists="append", index=False)

            print(f"Successfully appended to PostgreSQL table: {args.db_table}")

        except ImportError:
            print("\nError: Missing database dependencies.", file=sys.stderr)
            print("Please run: pip install sqlalchemy psycopg2-binary", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"\nDatabase export failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
