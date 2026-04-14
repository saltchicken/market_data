import os
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from polygon import RESTClient

def main():
    # Load environment variables (assumes you have a .env file with POLYGON_API_KEY)
    load_dotenv()
    API_KEY = os.getenv("POLYGON_API_KEY")
    
    if not API_KEY:
        print("Error: POLYGON_API_KEY is not set in the environment or .env file.")
        return

    # Initialize Polygon REST Client
    client = RESTClient(API_KEY)
    ticker = "GOOG"

    # Build the start and end dates based on the target day.
    target_date_str = "2026-04-13"
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d")

    # For just that single day, start and end are the same.
    start_date = target_date
    end_date = target_date

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    # # Define the time range (Let's fetch yesterday and today)
    # end_date = datetime.today()
    # start_date = end_date - timedelta(days=1) # 2 days to ensure we hit a trading day

    # start_str = start_date.strftime("%Y-%m-%d")
    # end_str = end_date.strftime("%Y-%m-%d")

    print(f"Fetching 1-minute aggregates for '{ticker}' from {start_str} to {end_str}...")

    try:
        # Use list_aggs to get intraday data
        # multiplier=1, timespan="minute" -> 1-minute candles
        aggs = client.list_aggs(
            ticker=ticker,
            multiplier=1,
            timespan="minute",
            from_=start_str,
            to=end_str,
            limit=50000  # Max limit per request to get as much intraday data as possible
        )

        # Convert the generator to a list of dictionaries
        data_dicts = []
        for agg in aggs:
            data_dicts.append({
                "timestamp": getattr(agg, "timestamp", None),
                "open": getattr(agg, "open", None),
                "high": getattr(agg, "high", None),
                "low": getattr(agg, "low", None),
                "close": getattr(agg, "close", None),
                "volume": getattr(agg, "volume", None),
                "vwap": getattr(agg, "vwap", None),
                "transactions": getattr(agg, "transactions", None),
            })

        if not data_dicts:
            print(f"No 1-minute data found for {ticker} in the given date range.")
            return

        # Load into Pandas DataFrame for easy viewing
        df = pd.DataFrame(data_dicts)
        
        # Convert the Unix timestamp (milliseconds) to a readable Datetime
        if "timestamp" in df.columns:
            # Polygon timestamps are in UTC
            df["datetime_utc"] = pd.to_datetime(df["timestamp"], unit="ms")
            
            # Optionally convert to Eastern Time (Market Time)
            df["datetime_est"] = df["datetime_utc"].dt.tz_localize('UTC').dt.tz_convert('US/Eastern')
            
            # Rearrange columns to bring datetime to the front
            cols = ["datetime_est", "open", "high", "low", "close", "volume", "vwap", "transactions"]
            df = df[cols]

        print(f"\nSuccessfully retrieved {len(df)} 1-minute bars.")
        
        print("\n--- First 5 Minutes ---")
        print(df.head(5).to_string(index=False))
        
        print("\n--- Last 5 Minutes ---")
        print(df.tail(5).to_string(index=False))

    except Exception as e:
        print(f"An error occurred while fetching data: {e}")

if __name__ == "__main__":
    main()
