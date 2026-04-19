DROP TABLE IF EXISTS watchlist CASCADE;

CREATE TABLE watchlist (
    ticker TEXT PRIMARY KEY,
    strategy TEXT DEFAULT NULL,
    target_buy DOUBLE PRECISION DEFAULT NULL,
    target_sell DOUBLE PRECISION DEFAULT NULL,
    target_volume DOUBLE PRECISION DEFAULT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 1. Create a function to automatically update the timestamp
CREATE OR REPLACE FUNCTION update_watchlist_changetimestamp()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = NOW();
   RETURN NEW;
END;
$$ language 'plpgsql';

-- 2. Attach the trigger to the watchlist table
CREATE TRIGGER trg_watchlist_updated_at
BEFORE UPDATE ON watchlist
FOR EACH ROW
EXECUTE FUNCTION update_watchlist_changetimestamp();

COMMENT ON TABLE watchlist IS 'Active symbols and alert thresholds monitored by IBKR.';
COMMENT ON COLUMN watchlist.strategy IS 'Strategy that was used to identify the symbol.';
COMMENT ON COLUMN watchlist.target_buy IS 'Target limit price to trigger a buy alert.';
COMMENT ON COLUMN watchlist.target_sell IS 'Target limit price to trigger a sell alert.';
COMMENT ON COLUMN watchlist.target_volume IS 'Target minimum volume threshold to trigger an alert.';
