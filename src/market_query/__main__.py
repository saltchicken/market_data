import os
import sys
import argparse
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def main():
    parser = argparse.ArgumentParser(
        description="Run analytical SQL queries against the database."
    )
    parser.add_argument(
        "query_name",
        nargs="?",
        help="Name of the query to run (e.g., golden_cross_screener) or 'list' to see available queries.",
    )
    # Add a new optional argument for the ticker
    parser.add_argument(
        "--ticker", "-t", type=str, help="Specific ticker to filter by", default=None
    )
    args = parser.parse_args()

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
        print("\nUsage: market_query <name> [--ticker TICKER]")
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

    # Load environment variables
    load_dotenv()
    db_url = os.getenv("DB_URL")

    if not db_url:
        print("Error: Missing DB_URL in .env file.")
        sys.exit(1)

    # Read the SQL query from the resolved file path
    with open(sql_path, "r") as file:
        query = file.read()

    # Connect to the database and run the query
    print(f"Executing query from {sql_path}...\n")
    try:
        engine = create_engine(db_url)

        # Set up our query parameters
        params = {}
        if args.ticker:
            params["ticker"] = args.ticker.upper()

        # Pass the params dictionary to pd.read_sql
        df = pd.read_sql(text(query), engine, params=params)

        if df.empty:
            print("Query executed successfully but returned no results.")
        else:
            # Print all rows and columns nicely formatted in the terminal
            pd.set_option("display.max_rows", None)
            pd.set_option("display.max_columns", None)
            pd.set_option("display.width", 1000)
            print(df)

    except Exception as e:
        print(f"An error occurred while running the query:\n{e}")


if __name__ == "__main__":
    main()
