-- ============================================================================
-- 2-Month Horizontal Resistance & Support Levels
-- 
-- Identifies "Swing Highs" (Resistance) and "Swing Lows" (Support) over 
-- the last 60 days by finding local peaks and troughs in the price action.
-- ============================================================================

WITH recent_data AS (
    -- 1. Isolate the last ~2 months of data for the target ticker
    SELECT 
        market_date, 
        high,
        low,
        close,
        volume
    FROM daily_market_data
    WHERE ticker = :ticker
      -- Use a dynamic lookback based on the latest date in the database
      AND market_date >= (
          SELECT MAX(market_date) - INTERVAL '60 days' 
          FROM daily_market_data 
          WHERE ticker = :ticker
      )
),
swing_points AS (
    -- 2. Use Window Functions to look at the surrounding 8 days (4 before, 4 after)
    SELECT 
        market_date,
        high,
        low,
        close,
        volume,
        MAX(high) OVER (ORDER BY market_date ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS prev_4_highs,
        MAX(high) OVER (ORDER BY market_date ROWS BETWEEN 1 FOLLOWING AND 4 FOLLOWING) AS next_4_highs,
        MIN(low) OVER (ORDER BY market_date ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS prev_4_lows,
        MIN(low) OVER (ORDER BY market_date ROWS BETWEEN 1 FOLLOWING AND 4 FOLLOWING) AS next_4_lows
    FROM recent_data
)
-- 3. Filter for true local peaks (Resistance) and troughs (Support)
SELECT 
    market_date,
    CASE 
        WHEN high > prev_4_highs AND high > next_4_highs THEN 'Resistance'
        WHEN low < prev_4_lows AND low < next_4_lows THEN 'Support'
    END AS level_type,
    CASE 
        WHEN high > prev_4_highs AND high > next_4_highs THEN ROUND(CAST(high AS NUMERIC), 2)
        WHEN low < prev_4_lows AND low < next_4_lows THEN ROUND(CAST(low AS NUMERIC), 2)
    END AS price_level,
    volume
FROM swing_points
WHERE 
    (high > prev_4_highs AND high > next_4_highs)
    OR 
    (low < prev_4_lows AND low < next_4_lows)
ORDER BY 
    price_level DESC;
