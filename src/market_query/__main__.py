import os
import sys
import logging
import argparse
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from core.log_config import setup_logging

logger = logging.getLogger("market_query")

def main():
    setup_logging("market_query")

    parser = argparse.ArgumentParser(
        description="Run analytical SQL queries against the database and optionally build a watchlist."
    )
    parser.add_argument("query_name", nargs="?", help="Name of the query to run (e.g., golden_cross) or 'list'")
    parser.add_argument("--ticker", "-t", type=str, help="Specific ticker to filter by", default=None)
    parser.add_argument("--watchlist", "-w", action="store_true", help="Push tickers to watchlist")
    parser.add_argument("--clear-all", action="store_true", help="Delete ALL tickers in the entire watchlist.")
    parser.add_argument("--limit", type=int, default=20, help="Max tickers to add to watchlist")

    args = parser.parse_args()

    load_dotenv()
    db_url = os.getenv("DB_URL")

    if not db_url:
        logger.error("Missing DB_URL in .env file.")
        sys.exit(1)

    try:
        engine = create_engine(db_url)
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        sys.exit(1)

    if args.clear_all:
        logger.info("🧹 Deleting ENTIRE watchlist...")
        try:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM watchlist"))
            logger.info("✅ Watchlist completely cleared.")
        except Exception as e:
            logger.error(f"Error clearing watchlist: {e}")
            sys.exit(1)

        if not args.query_name:
            sys.exit(0)

    package_dir = os.path.dirname(os.path.abspath(__file__))
    sql_dir = os.path.join(package_dir, "sql")

    if not args.query_name or args.query_name.lower() == "list":
        print("\nAvailable queries:")
        if os.path.exists(sql_dir):
            scripts = sorted([f for f in os.listdir(sql_dir) if f.endswith(".sql")])
            for script in scripts:
                print(f"  - {script.replace('.sql', '')}")
        else:
            print("  (No sql directory found)")
        print("\nUsage: market_query <name> [--ticker TICKER] [--watchlist] [--clear-all] [--limit LIMIT]")
        sys.exit(0)

    query_name = args.query_name
    target_name = query_name if query_name.endswith(".sql") else f"{query_name}.sql"
    package_sql_path = os.path.join(sql_dir, target_name)

    if os.path.exists(package_sql_path):
        sql_path = package_sql_path
    elif os.path.exists(query_name):
        sql_path = query_name
    else:
        logger.error(f"Could not find query '{query_name}'. Run 'market_query list' to see available options.")
        sys.exit(1)

    with open(sql_path, "r") as file:
        query = file.read()

    logger.info(f"🔍 Executing query from {sql_path}...")
    try:
        params = {}
        if args.ticker:
            params["ticker"] = args.ticker.upper()

        df = pd.read_sql(text(query), engine, params=params)

        if df.empty:
            logger.info("Query executed successfully but returned no results.")
            sys.exit(0)

        if args.watchlist:
            if "ticker" not in df.columns:
                logger.error("No 'ticker' column found in query results. Watchlist remains unchanged.")
                sys.exit(1)

            df_to_add = df.head(args.limit)
            tickers_to_add = df_to_add["ticker"].tolist()

            logger.info(f"✅ Strategy found {len(df)} tickers. Taking top {len(tickers_to_add)}...")

            strategy_name = os.path.basename(sql_path).replace(".sql", "")
            allowed_optional_cols = ["target_buy", "target_sell", "target_volume"]
            active_optional_cols = [col for col in allowed_optional_cols if col in df_to_add.columns]

            with engine.begin() as conn:
                if not args.clear_all:
                    logger.info(f"🧹 Automatically deleting old tickers for strategy: '{strategy_name}'...")
                    conn.execute(
                        text("DELETE FROM watchlist WHERE strategy = :strat"),
                        {"strat": strategy_name},
                    )

                logger.info(f"📝 Upserting tickers into watchlist tagged as '{strategy_name}'...")
                if active_optional_cols:
                    logger.info(f"   -> Including dynamic targets: {', '.join(active_optional_cols)}")

                insert_cols = ["ticker", "strategy"] + active_optional_cols
                insert_vals = [":ticker", ":strategy"] + [f":{col}" for col in active_optional_cols]

                update_clauses = ["strategy = EXCLUDED.strategy", "updated_at = CURRENT_TIMESTAMP"]
                for col in active_optional_cols:
                    update_clauses.append(f"{col} = EXCLUDED.{col}")

                upsert_query = text(f"""
                    INSERT INTO watchlist ({', '.join(insert_cols)})
                    VALUES ({', '.join(insert_vals)})
                    ON CONFLICT (ticker) DO UPDATE 
                    SET {', '.join(update_clauses)};
                """)

                records = df_to_add.to_dict(orient="records")
                for record in records:
                    sql_params = {"ticker": record["ticker"], "strategy": strategy_name}
                    for col in active_optional_cols:
                        val = record[col]
                        sql_params[col] = None if pd.isna(val) else val
                    conn.execute(upsert_query, sql_params)

            logger.info("🚀 Watchlist updated successfully! Tickers added/activated:")
            logger.info(", ".join(tickers_to_add))

        else:
            # We explicitly leave standard printing here to render the dataframe interactively for the user 
            pd.set_option("display.max_rows", None)
            pd.set_option("display.max_columns", None)
            pd.set_option("display.width", 1000)
            print(df)

            if args.clear_all:
                print("\n⚠️  Note: The watchlist in the database was cleared, but the results above were NOT saved to it.")
                print("    Run the command again with the '--watchlist' (-w) flag if you meant to save them.")

    except Exception as e:
        logger.error(f"An error occurred while running the query:\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
