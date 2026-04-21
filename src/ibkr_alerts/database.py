import logging
from sqlalchemy import create_engine, text

logger = logging.getLogger("ibkr_alerts")


def get_watchlist_targets_from_db(db_url: str) -> dict:
    """Fetch watchlist tickers AND yesterday's close from PostgreSQL."""
    if not db_url:
        logger.error("DB_URL is not set in the environment variables.")
        return {}

    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # We now ONLY need the ticker and the prev_close 
            query = text("""
                SELECT 
                    w.ticker, 
                    i.close AS prev_close
                FROM watchlist w
                LEFT JOIN (
                    SELECT ticker, close 
                    FROM daily_indicators 
                    WHERE market_date = (SELECT MAX(market_date) FROM daily_indicators)
                ) i ON w.ticker = i.ticker
                ORDER BY w.updated_at DESC 
                LIMIT 50;
            """)
            result = conn.execute(query)

            # Map results to a clean dictionary
            targets = {}
            for row in result:
                targets[row[0]] = {
                    "prev_close": row[1],
                }
        return targets
    except Exception as e:
        logger.error(f"Error fetching watchlist from database: {e}")
        return {}
