import pandas as pd
import time
import logging
from sqlalchemy import text
from .database import upload_to_postgres

logger = logging.getLogger(__name__)
_VALID_TICKERS_CACHE = None

def _get_valid_tickers(client):
    """Fetches and caches the list of valid Common Stock and ADR tickers."""
    global _VALID_TICKERS_CACHE
    if _VALID_TICKERS_CACHE is not None:
        return _VALID_TICKERS_CACHE

    logger.info("Fetching valid Common Stock (CS) and ADR (ADRC) tickers from Polygon...")
    _VALID_TICKERS_CACHE = {}
    ticker_types = ["CS", "ADRC"]

    try:
        for t_type in ticker_types:
            logger.info(f"Fetching type: {t_type}")
            ticker_iterator = client.list_tickers(market="stocks", type=t_type, active=True, limit=1000)

            for i, t in enumerate(ticker_iterator):
                if getattr(t, "ticker", None):
                    _VALID_TICKERS_CACHE[t.ticker] = t_type
                time.sleep(0.015)

                if i > 0 and i % 1000 == 0:
                    logger.info(f"... fetched {len(_VALID_TICKERS_CACHE)} total tickers so far")

        _VALID_TICKERS_CACHE["SPY"] = "ETF"
        _VALID_TICKERS_CACHE["QQQ"] = "ETF"

        logger.info(f"Found {len(_VALID_TICKERS_CACHE)} active CS and ADRC tickers (including SPY).")
    except Exception as e:
        logger.error(f"Error fetching valid tickers list: {e}")
        raise e

    return _VALID_TICKERS_CACHE


def get_entire_market_ohlcv(date, client):
    """Fetches daily OHLCV for the entire US stock market for a specific date."""
    valid_tickers = _get_valid_tickers(client)

    try:
        all_market_data = client.get_grouped_daily_aggs(date)
        if not all_market_data: return None

        filtered_data = [agg for agg in all_market_data if getattr(agg, "ticker", None) in valid_tickers]
        logger.info(f"Successfully pulled {len(filtered_data)} valid CS/ADRC/ETF tickers for {date} (out of {len(all_market_data)} total)")

        data_dicts = [
            {
                "ticker": getattr(agg, "ticker", None),
                "asset_class": valid_tickers.get(getattr(agg, "ticker", None)),
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
        logger.error(f"Client Error: {e}")
        return None


def fetch_and_upload(target_date, engine, client):
    entire_market_data = get_entire_market_ohlcv(target_date, client)

    if entire_market_data is not None and not entire_market_data.empty:
        entire_market_data["market_date"] = pd.to_datetime(target_date).date()

        entire_market_data = entire_market_data.dropna(subset=["ticker"])
        entire_market_data = entire_market_data.sort_values(
            "volume", ascending=False
        ).drop_duplicates(subset=["ticker"])

        try:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM daily_market_data WHERE market_date = :dt"),
                    {"dt": target_date},
                )
        except Exception as e:
            logger.warning(f"Could not clear existing data for {target_date}: {e}")

        upload_to_postgres(df=entire_market_data, table_name="daily_market_data", engine=engine)
        return True
    else:
        logger.warning(f"No market data found for {target_date}.")
        return False
