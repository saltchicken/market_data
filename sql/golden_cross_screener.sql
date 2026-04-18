-- ============================================================================
-- Golden Cross Screener (SMA 50 crossing above SMA 200)
-- 
-- This query identifies tickers where the 50-Day Simple Moving Average was 
-- strictly below the 200-Day Simple Moving Average yesterday, but has 
-- crossed to be greater than or equal to the 200-Day SMA today.
-- ============================================================================

WITH recent_dates AS (
    -- 1. Identify the two most recent trading days in the database
    SELECT DISTINCT market_date
    FROM daily_indicators
    ORDER BY market_date DESC
    LIMIT 2
),
target_data AS (
    -- 2. Pull data only for those two days to ensure the query runs instantly
    SELECT
        ticker,
        market_date,
        close,
        sma_50,
        sma_200,
        volume_dod_pct,
        atr_14_pct
    FROM daily_indicators
    WHERE market_date IN (SELECT market_date FROM recent_dates)
),
lagged_indicators AS (
    -- 3. Use the LAG() window function to attach yesterday's SMAs to today's row
    SELECT
        ticker,
        market_date,
        close,
        sma_50,
        sma_200,
        volume_dod_pct,
        atr_14_pct,
        LAG(sma_50) OVER (PARTITION BY ticker ORDER BY market_date) AS prev_sma_50,
        LAG(sma_200) OVER (PARTITION BY ticker ORDER BY market_date) AS prev_sma_200
    FROM target_data
)
-- 4. Filter for the exact crossover event on the latest date
SELECT
    ticker,
    market_date,
    close,
    ROUND(CAST(sma_50 AS NUMERIC), 2) AS sma_50,
    ROUND(CAST(sma_200 AS NUMERIC), 2) AS sma_200,
    ROUND(CAST(prev_sma_50 AS NUMERIC), 2) AS prev_sma_50,
    ROUND(CAST(prev_sma_200 AS NUMERIC), 2) AS prev_sma_200,
    ROUND(CAST(volume_dod_pct AS NUMERIC), 2) AS vol_change_pct,
    ROUND(CAST(atr_14_pct AS NUMERIC), 2) AS atr_14_pct
FROM lagged_indicators
WHERE market_date = (SELECT MAX(market_date) FROM recent_dates)
  -- The core Golden Cross condition:
  AND prev_sma_50 < prev_sma_200
  AND sma_50 >= sma_200
  -- Optional: ensure we actually have the SMA 200 calculated
  AND sma_200 IS NOT NULL 
ORDER BY volume_dod_pct DESC;










