DROP TABLE IF EXISTS watchlist CASCADE;

CREATE TABLE watchlist (
    ticker TEXT PRIMARY KEY,
    strategy TEXT DEFAULT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    target_buy DOUBLE PRECISION DEFAULT NULL,
    target_sell DOUBLE PRECISION DEFAULT NULL,
    target_volume DOUBLE PRECISION DEFAULT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE watchlist IS 'Active symbols and alert thresholds monitored by IBKR.';
COMMENT ON COLUMN watchlist.strategy IS 'Strategy that was used to identify the symbol.';
COMMENT ON COLUMN watchlist.is_active IS 'Boolean flag to easily pause monitoring for a symbol without deleting it.';
COMMENT ON COLUMN watchlist.target_buy IS 'Target limit price to trigger a buy alert.';
COMMENT ON COLUMN watchlist.target_sell IS 'Target limit price to trigger a sell alert.';
COMMENT ON COLUMN watchlist.target_volume IS 'Target minimum volume threshold to trigger an alert.';
