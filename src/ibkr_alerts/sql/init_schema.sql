DROP TABLE IF EXISTS watchlist CASCADE;

CREATE TABLE watchlist (
    ticker TEXT PRIMARY KEY,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE watchlist IS 'Active symbols and alert thresholds monitored by IBKR.';
COMMENT ON COLUMN watchlist.is_active IS 'Boolean flag to easily pause monitoring for a symbol without deleting it.';
