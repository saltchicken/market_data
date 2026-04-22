import argparse
import os
import sys
import time
import logging
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from finvizfinance.screener.overview import Overview
from finvizfinance.screener.valuation import Valuation
from finvizfinance.screener.financial import Financial
from finvizfinance.screener.ownership import Ownership

from core.log_config import setup_logging

logger = logging.getLogger("finviz_screener")

def fetch_group_tickers(filters_dict: dict) -> pd.DataFrame:
    """Pulls the screener data for the specified filters across all tabs."""
    tabs = [
        ("Overview", Overview),
        ("Valuation", Valuation),
        ("Financial", Financial),
        ("Ownership", Ownership),
    ]

    merged_df = None

    for tab_name, screener_class in tabs:
        try:
            logger.info(f"Fetching {tab_name} tab...")
            screener = screener_class()

            if filters_dict:
                screener.set_filter(filters_dict=filters_dict)

            df = screener.screener_view()

            if df.empty:
                continue

            if merged_df is None:
                merged_df = df
            else:
                new_cols = df.columns.difference(merged_df.columns).tolist()
                new_cols.append("Ticker")
                merged_df = pd.merge(merged_df, df[new_cols], on="Ticker", how="outer")

            logger.info("Waiting 3 seconds to respect rate limits...")
            time.sleep(3)

        except Exception as e:
            logger.error(f"Error fetching {tab_name} data from Finviz: {e}")

    return merged_df if merged_df is not None else pd.DataFrame()


def clean_columns_for_db(df: pd.DataFrame) -> pd.DataFrame:
    """Formats column names to be strictly PostgreSQL-friendly and rounds numbers."""
    df_db = df.copy()

    def parse_suffix(val):
        if isinstance(val, str):
            val = val.strip()
            if val and val[-1].upper() in ("T", "B", "M", "K"):
                try:
                    num = float(val[:-1])
                    mult = val[-1].upper()
                    if mult == "T": return num * 1e12
                    if mult == "B": return num * 1e9
                    if mult == "M": return num * 1e6
                    if mult == "K": return num * 1e3
                except ValueError:
                    pass
        return val

    df_db.columns = (
        df_db.columns.str.lower()
        .str.replace(" ", "_")
        .str.replace("/", "_")
        .str.replace("%", "pct")
        .str.replace("(", "")
        .str.replace(")", "")
        .str.replace("-", "_")
    )

    redundant_columns = [
        "price", "change", "volume", "avg_volume", "rel_volume", "perf_week",
        "perf_month", "perf_quart", "perf_half", "perf_ytd", "perf_year",
        "perf_3y", "perf_5y", "perf_10y", "gap", "change_from_open", "sma20",
        "sma50", "sma200", "rsi", "atr", "volatility_w", "volatility_m",
    ]
    df_db = df_db.drop(
        columns=[col for col in redundant_columns if col in df_db.columns]
    )

    for col in df_db.columns:
        if df_db[col].dtype == "object": 
            df_db[col] = df_db[col].replace("-", None)
            original_valid = df_db[col].notna().sum()
            if original_valid == 0: continue

            df_db[col] = df_db[col].apply(parse_suffix)

            if df_db[col].astype(str).str.contains("%").any():
                stripped_col = df_db[col].astype(str).str.replace("%", "", regex=False)
                converted_col = pd.to_numeric(stripped_col, errors="coerce")
                if converted_col.notna().sum() >= (original_valid * 0.5):
                    df_db[col] = converted_col
            else:
                converted_col = pd.to_numeric(df_db[col], errors="coerce")
                if converted_col.notna().sum() >= (original_valid * 0.5):
                    df_db[col] = converted_col

    numeric_cols = df_db.select_dtypes(include=["number"]).columns
    df_db[numeric_cols] = df_db[numeric_cols].round(2)

    return df_db


def upsert_finviz_data(df: pd.DataFrame, table_name: str, engine):
    """Upserts dataframe into PostgreSQL using ON CONFLICT DO UPDATE."""
    from sqlalchemy import MetaData, Table
    from sqlalchemy.dialects.postgresql import insert
    import numpy as np

    clean_df = df.replace({np.nan: None})
    records = clean_df.to_dict(orient="records")

    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine)

    stmt = insert(table).values(records)

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
        logger.error(f"SQL file not found at {sql_file_path}")
        return

    try:
        engine = create_engine(db_url)
        with engine.begin() as conn:
            with open(sql_file_path, "r") as file:
                sql_script = file.read()
                conn.execute(text(sql_script))
        logger.info("Successfully initialized finviz_screener database schema.")
    except Exception as e:
        logger.error(f"Database Initialization Error: {e}")
        sys.exit(1)


def main():
    setup_logging("finviz_screener")
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Find all tickers in a specific Finviz group or ALL tickers."
    )
    parser.add_argument("--sector", type=str, help="Filter by Sector")
    parser.add_argument("--industry", type=str, help="Filter by Industry")
    parser.add_argument("--country", type=str, help="Filter by Country")
    parser.add_argument("--all", action="store_true", default=True, help="Fetch ALL tickers")
    parser.add_argument("--db-url", type=str, default=os.getenv("DB_URL"), help="PostgreSQL Connection URL")
    parser.add_argument("--db-table", type=str, default="finviz_screener", help="Target Postgres Table")
    parser.add_argument("--out-csv", type=str, help="Output CSV Prefix")

    args = parser.parse_args()

    if args.db_url:
        logger.info("Initializing clean database schema...")
        init_database(args.db_url)

    filters = {}
    if args.sector: filters["Sector"] = args.sector
    if args.industry: filters["Industry"] = args.industry
    if args.country: filters["Country"] = args.country

    if not filters:
        logger.info("Fetching ALL data tabs for ALL tickers (no filters applied)...")
    else:
        logger.info(f"Fetching all data tabs for filters: {filters}...")

    df = fetch_group_tickers(filters)

    if df.empty:
        logger.warning("No tickers found for the specified filters, or an error occurred.")
        sys.exit(0)

    current_date = datetime.today().strftime("%Y-%m-%d")
    df["Date"] = pd.Timestamp.today().date()

    tickers = df["Ticker"].tolist()
    logger.info(f"Found {len(tickers)} tickers on {current_date}.")

    if args.out_csv:
        csv_filename = f"{args.out_csv}_{current_date}.csv"
        df.to_csv(csv_filename, index=False)
        logger.info(f"Successfully saved daily run to CSV: {csv_filename}")

    if args.db_url and args.db_table:
        logger.info(f"Exporting to PostgreSQL database table: '{args.db_table}'...")
        try:
            from sqlalchemy import create_engine
            engine = create_engine(args.db_url)
            df_db = clean_columns_for_db(df)
            upsert_finviz_data(df_db, args.db_table, engine)
            logger.info(f"Successfully upserted data to PostgreSQL table: {args.db_table}")

        except ImportError:
            logger.error("Missing database dependencies. Please run: pip install sqlalchemy psycopg2-binary")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Database export failed: {e}")

if __name__ == "__main__":
    main()
