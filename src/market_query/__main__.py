import os
import sys
import argparse
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def main():
    parser = argparse.ArgumentParser(
        description="Run analytical SQL queries against the database and optionally build a watchlist."
    )
    
    # Query arguments
    parser.add_argument(
        "query_name",
        nargs="?",
        help="Name of the query to run (e.g., golden_cross) or 'list' to see available queries.",
    )
    parser.add_argument(
        "--ticker", "-t", type=str, help="Specific ticker to filter by", default=None
    )

    # Watchlist arguments
    parser.add_argument(
        "--watchlist", 
        "-w", 
        action="store_true", 
        help="Push the resulting tickers to the active IBKR watchlist rather than printing."
    )
    parser.add_argument(
        "--clear-all", 
        action="store_true", 
        help="Delete ALL tickers in the entire watchlist."
    )
    parser.add_argument(
        "--limit", 
        type=int, 
        default=20, 
        help="Maximum number of tickers to add to the watchlist (IBKR has a ~50 ticker streaming limit)."
    )

    args = parser.parse_args()

    # Load environment variables EARLY so we can process standalone flags
    load_dotenv()
    db_url = os.getenv("DB_URL")

    if not db_url:
        print("Error: Missing DB_URL in .env file.")
        sys.exit(1)
        
    try:
        engine = create_engine(db_url)
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

    # --- INDEPENDENT CLEAR LOGIC ---
    # Executes immediately regardless of whether we are running a query or pushing to the watchlist
    if args.clear_all:
        print("🧹 Deleting ENTIRE watchlist...")
        try:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM watchlist"))
            print("✅ Watchlist completely cleared.")
        except Exception as e:
            print(f"Error clearing watchlist: {e}")
            sys.exit(1)
            
        # If the user just ran `market_query --clear-all` with no query, exit cleanly.
        if not args.query_name:
            sys.exit(0)


    package_dir = os.path.dirname(os.path.abspath(__file__))
    sql_dir = os.path.join(package_dir, "sql")

    # Handle 'list' or missing argument
    if not args.query_name or args.query_name.lower() == "list":
        print("\nAvailable queries:")
        if os.path.exists(sql_dir):
            scripts = sorted([f for f in os.listdir(sql_dir) if f.endswith('.sql')])
            for script in scripts:
                print(f"  - {script.replace('.sql', '')}")
        else:
            print("  (No sql directory found)")
        print("\nUsage: market_query <name> [--ticker TICKER] [--watchlist] [--clear-all] [--limit LIMIT]")
        sys.exit(0)

    # Resolve the path to the SQL file
    query_name = args.query_name
    
    # Priority 1: Check the package's sql/ directory by default
    target_name = query_name if query_name.endswith('.sql') else f"{query_name}.sql"
    package_sql_path = os.path.join(sql_dir, target_name)
    
    if os.path.exists(package_sql_path):
        sql_path = package_sql_path
    # Priority 2: Fallback to exact local path if they provided an absolute/relative path
    elif os.path.exists(query_name):
        sql_path = query_name
    else:
        print(f"Error: Could not find query '{query_name}'.")
        print("Run 'market_query list' to see available options.")
        sys.exit(1)

    # Read the SQL query from the resolved file path
    with open(sql_path, "r") as file:
        query = file.read()

    # Connect to the database and run the query
    print(f"🔍 Executing query from {sql_path}...\n")
    try:
        # Set up our query parameters
        params = {}
        if args.ticker:
            params["ticker"] = args.ticker.upper()

        # Pass the params dictionary to pd.read_sql
        df = pd.read_sql(text(query), engine, params=params)

        if df.empty:
            print("Query executed successfully but returned no results.")
            sys.exit(0)

        # --- COMBINED LOGIC: Push to Watchlist OR Print to Terminal ---
        if args.watchlist:
            if 'ticker' not in df.columns:
                print("Error: No 'ticker' column found in query results. Watchlist remains unchanged.")
                sys.exit(1)

            # Apply limit to avoid hitting IBKR pacing/streaming limits
            df_to_add = df.head(args.limit)
            tickers_to_add = df_to_add['ticker'].tolist()
            
            print(f"✅ Strategy found {len(df)} tickers. Taking top {len(tickers_to_add)}...")

            strategy_name = os.path.basename(sql_path).replace('.sql', '')
            
            # Dynamically match columns from the query to allowed watchlist columns
            allowed_optional_cols = ['target_buy', 'target_sell', 'target_volume']
            active_optional_cols = [col for col in allowed_optional_cols if col in df_to_add.columns]
            
            with engine.begin() as conn:
                # We only need to clear the specific strategy if we didn't just clear the entire DB
                if not args.clear_all:
                    # AUTOMATICALLY clear old tickers for this specific strategy
                    print(f"🧹 Automatically deleting old tickers for strategy: '{strategy_name}'...")
                    conn.execute(
                        text("DELETE FROM watchlist WHERE strategy = :strat"),
                        {"strat": strategy_name}
                    )

                print(f"📝 Upserting tickers into watchlist tagged as '{strategy_name}'...")
                if active_optional_cols:
                    print(f"   -> Including dynamic targets: {', '.join(active_optional_cols)}")
                
                # Build dynamic UPSERT SQL query
                insert_cols = ['ticker', 'strategy'] + active_optional_cols
                insert_vals = [':ticker', ':strategy'] + [f':{col}' for col in active_optional_cols]
                
                update_clauses = [
                    "strategy = EXCLUDED.strategy",
                    "updated_at = CURRENT_TIMESTAMP"
                ]
                
                # If a value updates, we want to overwrite it in the DB
                for col in active_optional_cols:
                    update_clauses.append(f"{col} = EXCLUDED.{col}")
                    
                upsert_query = text(f"""
                    INSERT INTO watchlist ({', '.join(insert_cols)})
                    VALUES ({', '.join(insert_vals)})
                    ON CONFLICT (ticker) DO UPDATE 
                    SET {', '.join(update_clauses)};
                """)
                
                # Iterate through dataframe as dictionary records to inject into DB
                records = df_to_add.to_dict(orient="records")
                for record in records:
                    sql_params = {
                        "ticker": record['ticker'],
                        "strategy": strategy_name
                    }
                    
                    # Format optional target values. Convert NaN values to None for Postgres.
                    for col in active_optional_cols:
                        val = record[col]
                        sql_params[col] = None if pd.isna(val) else val
                        
                    conn.execute(upsert_query, sql_params)
                    
            print(f"\n🚀 Watchlist updated successfully! Tickers added/activated:")
            print(", ".join(tickers_to_add))
            print("\nYou can now start IBKR alerts by running: ibkr_alerts")

        else:
            # Print all rows and columns nicely formatted in the terminal
            pd.set_option("display.max_rows", None)
            pd.set_option("display.max_columns", None)
            pd.set_option("display.width", 1000)
            print(df)
            
            if args.clear_all:
                print("\n⚠️  Note: The watchlist in the database was cleared, but the results above were NOT saved to it.")
                print("    Run the command again with the '--watchlist' (-w) flag if you meant to save them.")

    except Exception as e:
        print(f"An error occurred while running the query:\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
