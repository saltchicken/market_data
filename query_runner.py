import os
import sys
import argparse
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

def main():
    parser = argparse.ArgumentParser(description="Run analytical SQL queries against the database.")
    parser.add_argument("sql_file", help="Path to the .sql file you want to run (e.g., sql/attention_score.sql)")
    args = parser.parse_args()

    # Ensure the file exists
    if not os.path.exists(args.sql_file):
        print(f"Error: Could not find file '{args.sql_file}'")
        sys.exit(1)

    # Load environment variables
    load_dotenv()
    db_url = os.getenv("DB_URL")

    if not db_url:
        print("Error: Missing DB_URL in .env file.")
        sys.exit(1)

    # Read the SQL query from the file
    with open(args.sql_file, 'r') as file:
        query = file.read()

    # Connect to the database and run the query
    print(f"Executing query from {args.sql_file}...\n")
    try:
        engine = create_engine(db_url)
        
        # Use Pandas to execute the query and format the output
        df = pd.read_sql(text(query), engine)
        
        if df.empty:
            print("Query executed successfully but returned no results.")
        else:
            # Print all rows and columns nicely formatted in the terminal
            pd.set_option('display.max_rows', None)
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', 1000)
            print(df)
            
    except Exception as e:
        print(f"An error occurred while running the query:\n{e}")

if __name__ == "__main__":
    main()
