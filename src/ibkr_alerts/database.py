import logging
from sqlalchemy import create_engine, text

logger = logging.getLogger("ibkr_alerts")

def get_watchlist_targets_from_db(db_url: str) -> dict:
    """Fetch watchlist tickers, their targets, AND yesterday's close from PostgreSQL."""
    if not db_url:
        logger.error("DB_URL is not set in the environment variables.")
        return {}

    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Join the watchlist with the most recent daily_indicators record to get 'prev_close'
            query = text("""
                SELECT 
                    w.ticker, 
                    w.target_buy, 
                    w.target_sell, 
                    w.target_volume,
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
            
            # Map results to a dictionary
            targets = {}
            for row in result:
                targets[row[0]] = {
                    'target_buy': row[1],
                    'target_sell': row[2],
                    'target_volume': row[3],
                    'prev_close': row[4]  # Added yesterday's close
                }
        return targets
    except Exception as e:
        logger.error(f"Error fetching watchlist from database: {e}")
        return {}
