import logging
from sqlalchemy import create_engine, text

logger = logging.getLogger("ibkr_alerts")

def get_watchlist_targets_from_db(db_url: str) -> dict:
    """Fetch active watchlist tickers AND their targets from the PostgreSQL database."""
    if not db_url:
        logger.error("DB_URL is not set in the environment variables.")
        return {}

    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            query = text("""
                SELECT ticker, target_buy, target_sell, target_volume 
                FROM watchlist 
                ORDER BY updated_at DESC 
                LIMIT 50;
            """)
            result = conn.execute(query)
            
            # Map results to a dictionary: { 'AAPL': {'target_buy': 150, 'target_volume': 50000}, ... }
            targets = {}
            for row in result:
                targets[row[0]] = {
                    'target_buy': row[1],
                    'target_sell': row[2],
                    'target_volume': row[3]
                }
        return targets
    except Exception as e:
        logger.error(f"Error fetching watchlist from database: {e}")
        return {}
