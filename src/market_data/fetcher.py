import pandas as pd
from sqlalchemy import text
from .database import upload_to_postgres


def get_entire_market_ohlcv(date, client, valid_tickers):
    """Fetches daily OHLCV for the entire US stock market for a specific date, filtering for valid tickers."""
    try:
        all_market_data = client.get_grouped_daily_aggs(date)
        if not all_market_data:
            return None

        # Instantly filter out warrants, units, preferred stocks using our pre-fetched set
        filtered_data = [
            agg for agg in all_market_data 
            if getattr(agg, "ticker", None) in valid_tickers
        ]

        print(f"--- Successfully pulled {len(filtered_data)} valid CS tickers for {date} (out of {len(all_market_data)} total) ---")

        data_dicts = [
            {
                "ticker": getattr(agg, "ticker", None),
                "open": getattr(agg, "open", None),
                "high": getattr(agg, "high", None),
                "low": getattr(agg, "low", None),
                "close": getattr(agg, "close", None),
                "volume": getattr(agg, "volume", None),
                "vwap": getattr(agg, "vwap", None),
                "timestamp": getattr(agg, "timestamp", None),
                "transactions": getattr(agg, "transactions", None),
            }
            for agg in filtered_data
        ]

        df = pd.DataFrame(data_dicts)
        if not df.empty and "timestamp" in df.columns:
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df

    except Exception as e:
        print(f"Client Error: {e}")
        return None


def fetch_and_upload(target_date, engine, client, valid_tickers):
    entire_market_data = get_entire_market_ohlcv(target_date, client, valid_tickers)
    
    if entire_market_data is not None and not entire_market_data.empty:
        entire_market_data["market_date"] = pd.to_datetime(target_date).date()

        # Clean up data: drop invalid rows and remove duplicate tickers
        # (Polygon sometimes returns multiple entries for the same ticker, which crashes COPY)
        entire_market_data = entire_market_data.dropna(subset=["ticker"])
        entire_market_data = entire_market_data.sort_values(
            "volume", ascending=False
        ).drop_duplicates(subset=["ticker"])

        # Ensure idempotency: Delete existing data for this date so re-runs don't fail
        # due to UniqueViolation constraints.
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM daily_market_data WHERE market_date = :dt"),
                    {"dt": target_date},
                )
        except Exception as e:
            print(f"Warning: Could not clear existing data for {target_date}: {e}")

        upload_to_postgres(
            df=entire_market_data, table_name="daily_market_data", engine=engine
        )
        return True
    else:
        print(f"No market data found for {target_date}.")
        return False
