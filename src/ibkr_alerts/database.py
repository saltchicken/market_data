import logging
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


def get_watchlist_targets_from_db(db_url: str) -> dict:
    """Fetch watchlist tickers, yesterday's close, and ATR_14 from PostgreSQL."""
    if not db_url:
        logger.error("DB_URL is not set in the environment variables.")
        return {}

    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            query = text("""
                SELECT 
                    w.ticker, 
                    i.close AS prev_close,
                    i.atr_14
                FROM watchlist w
                LEFT JOIN (
                    SELECT ticker, close, atr_14 
                    FROM daily_indicators 
                    WHERE market_date = (SELECT MAX(market_date) FROM daily_indicators)
                ) i ON w.ticker = i.ticker
                ORDER BY w.updated_at DESC 
                LIMIT 50;
            """)
            result = conn.execute(query)

            targets = {}
            for row in result:
                # row[0] = ticker, row[1] = prev_close, row[2] = atr_14
                targets[row[0]] = {"prev_close": row[1], "atr_14": row[2]}
            return targets

    except Exception as e:
        logger.error(f"Error fetching watchlist from database: {e}")
        return {}
