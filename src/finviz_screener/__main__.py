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

    # Helper to parse T/B/M/K suffixes (e.g., 1.5B -> 1500000000.0)
    def parse_suffix(val):
        if isinstance(val, str):
            val = val.strip()
            if val and val[-1].upper() in ("T", "B", "M", "K"):
                try:
                    num = float(val[:-1])
                    mult = val[-1].upper()
                    if mult == "T":
                        return num * 1e12
                    if mult == "B":
                        return num * 1e9
                    if mult == "M":
                        return num * 1e6
                    if mult == "K":
                        return num * 1e3
                except ValueError:
                    pass
        return val

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

    # 2. Drop redundant columns that are locally calculated in the daily_indicators pipeline
    redundant_columns = [
        "price",
        "change",
        "volume",
        "avg_volume",
        "rel_volume",
        "perf_week",
        "perf_month",
        "perf_quart",
        "perf_half",
        "perf_ytd",
        "perf_year",
        "perf_3y",
        "perf_5y",
        "perf_10y",
        "gap",
        "change_from_open",
        "sma20",
        "sma50",
        "sma200",
        "rsi",
        "atr",
        "volatility_w",
        "volatility_m",
    ]
    df_db = df_db.drop(
        columns=[col for col in redundant_columns if col in df_db.columns]
    )

    # 3. Clean Data Types Safely
    for col in df_db.columns:
        if df_db[col].dtype == "object":  # If Pandas thinks it's text
            # Replace Finviz missing value indicator exactly with None
            df_db[col] = df_db[col].replace("-", None)

            original_valid = df_db[col].notna().sum()
            if original_valid == 0:
                continue

            # Parse T/B/M/K suffixes before attempting numeric coercion
            df_db[col] = df_db[col].apply(parse_suffix)

            # Safely check and convert percentage columns without crashing on text
            if df_db[col].astype(str).str.contains("%").any():
                stripped_col = df_db[col].astype(str).str.replace("%", "", regex=False)

                # Coerce errors so unconvertible text becomes NaN instead of crashing
                converted_col = pd.to_numeric(stripped_col, errors="coerce")

                # Only apply the conversion if it didn't wipe out > 50% of the column's valid data.
                # (This protects text columns like 'Company' if a single company has a '%' in its name)
                if converted_col.notna().sum() >= (original_valid * 0.5):
                    df_db[col] = converted_col
            else:
                # Catch other numbers formatted as text (e.g., P/E ratio that was skipped due to '-')
                converted_col = pd.to_numeric(df_db[col], errors="coerce")

                if converted_col.notna().sum() >= (original_valid * 0.5):
                    df_db[col] = converted_col

    # 5. Numeric Rounding
    numeric_cols = df_db.select_dtypes(include=["number"]).columns
    df_db[numeric_cols] = df_db[numeric_cols].round(2)

    return df_db


def upsert_finviz_data(df: pd.DataFrame, table_name: str, engine):
    """Upserts dataframe into PostgreSQL using ON CONFLICT DO UPDATE."""
    from sqlalchemy import MetaData, Table
    from sqlalchemy.dialects.postgresql import insert

    # Replace NaN with None so SQLAlchemy inserts NULLs instead of crashing on 'NaN' floats
    clean_df = df.where(pd.notnull(df), None)
    records = clean_df.to_dict(orient="records")

    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)

    stmt = insert(table).values(records)

    # Update all columns except the primary keys if a conflict occurs
    update_dict = {c.name: c for c in stmt.excluded if c.name not in ["ticker", "date"]}

    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=["ticker", "date"], set_=update_dict
    )

    with engine.begin() as conn:
        conn.execute(upsert_stmt)


def init_database(db_url: str):
    """Executes the init_schema.sql file to initialize the database schema."""
    from sqlalchemy import create_engine, text

    sql_file_path = os.path.join(os.path.dirname(__file__), "sql", "init_schema.sql")

    if not os.path.exists(sql_file_path):
        print(f"Error: SQL file not found at {sql_file_path}")
        return

    try:
        engine = create_engine(db_url)
        with engine.begin() as conn:
            with open(sql_file_path, "r") as file:
                sql_script = file.read()
                conn.execute(text(sql_script))
        print("Successfully initialized finviz_screener database schema.")
    except Exception as e:
        print(f"Database Initialization Error: {e}", file=sys.stderr)
        sys.exit(1)


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

    # Always initialize/reset the database schema for a clean table
    if args.db_url:
        print("\n=== Initializing clean database schema ===")
        init_database(args.db_url)

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
    df["Date"] = pd.Timestamp.today().date()

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
            from sqlalchemy import create_engine, text

            # Create SQLAlchemy engine
            engine = create_engine(args.db_url)

            # Clean dataframe column names to be Postgres friendly (e.g. "Market Cap" -> "market_cap")
            df_db = clean_columns_for_db(df)

            # Upsert into the table to avoid UniqueViolation errors on reruns
            upsert_finviz_data(df_db, args.db_table, engine)

            print(f"Successfully upserted data to PostgreSQL table: {args.db_table}")

        except ImportError:
            print("\nError: Missing database dependencies.", file=sys.stderr)
            print("Please run: pip install sqlalchemy psycopg2-binary", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"\nDatabase export failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
