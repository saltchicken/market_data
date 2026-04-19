import os
import sys
import argparse
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

def main():
    parser = argparse.ArgumentParser(
        description="Run a SQL strategy and push the resulting tickers to the active IBKR watchlist."
    )
    parser.add_argument(
        "strategy",
        help="Name of the SQL strategy file in the sql/ directory (e.g., golden_cross_screener)",
    )
    parser.add_argument(
        "--clear", 
        action="store_true", 
        help="Deactivate all currently active tickers in the watchlist before adding new ones."
    )
    parser.add_argument(
        "--limit", 
        type=int, 
        default=20, 
        help="Maximum number of tickers to add to the watchlist (IBKR has a ~50 ticker streaming limit)."
    )
    
    args = parser.parse_args()
    
    load_dotenv()
    db_url = os.getenv("DB_URL")
    if not db_url:
        print("Error: Missing DB_URL in .env file.")
        sys.exit(1)

    # Resolve SQL path
    package_dir = os.path.dirname(os.path.abspath(__file__))
    target_name = args.strategy if args.strategy.endswith('.sql') else f"{args.strategy}.sql"
    sql_path = os.path.join(package_dir, "sql", target_name)
    
    if not os.path.exists(sql_path):
        print(f"Error: Strategy file not found at {sql_path}")
        sys.exit(1)

    # 1. Read and execute the strategy
    print(f"🔍 Running strategy: {args.strategy}...")
    with open(sql_path, "r") as file:
        query = file.read()

    engine = create_engine(db_url)
    try:
        df = pd.read_sql(text(query), engine)
    except Exception as e:
        print(f"Database query failed: {e}")
        sys.exit(1)

    if df.empty or 'ticker' not in df.columns:
        print("No tickers found or the query is missing a 'ticker' column. Watchlist remains unchanged.")
        sys.exit(0)

    # Apply limit to avoid hitting IBKR pacing/streaming limits
    tickers_to_add = df['ticker'].head(args.limit).tolist()
    print(f"✅ Strategy found {len(df)} tickers. Taking top {len(tickers_to_add)}...")

    # 2. Update the watchlist table
    strategy_name = args.strategy.replace('.sql', '')
    
    with engine.begin() as conn:
        if args.clear:
            print("🧹 Clearing currently active watchlist...")
            conn.execute(text("UPDATE watchlist SET is_active = FALSE"))

        print(f"📝 Upserting tickers into watchlist tagged as '{strategy_name}'...")
        
        # Upsert logic: Insert new, or update existing to be active with the new strategy
        upsert_query = text("""
            INSERT INTO watchlist (ticker, strategy, is_active)
            VALUES (:ticker, :strategy, TRUE)
            ON CONFLICT (ticker) DO UPDATE 
            SET strategy = EXCLUDED.strategy, 
                is_active = TRUE,
                updated_at = CURRENT_TIMESTAMP;
        """)
        
        for ticker in tickers_to_add:
            conn.execute(upsert_query, {"ticker": ticker, "strategy": strategy_name})
            
    print(f"\n🚀 Watchlist updated successfully! Tickers added/activated:")
    print(", ".join(tickers_to_add))
    print("\nYou can now start IBKR alerts by running: ibkr_alerts")

if __name__ == "__main__":
    main()
