-- ============================================================================
-- 2-Month Horizontal Resistance & Support Levels
-- 
-- Identifies "Swing Highs" (Resistance) and "Swing Lows" (Support) over 
-- the last 60 days by finding local peaks and troughs in the price action.
-- ============================================================================

WITH raw_data AS (
    -- FIX 1: Pull 80 days of data to provide a buffer for the window functions, 
    -- preventing "Data Starvation" at the beginning of the 60-day visual window.
    SELECT 
        market_date, 
        high,
        low,
        close,
        volume
    FROM daily_market_data
    WHERE ticker = :ticker
      AND market_date >= (
          SELECT MAX(market_date) - INTERVAL '80 days' 
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
        volume,
        MAX(high) OVER (ORDER BY market_date ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS prev_4_highs,
        MAX(high) OVER (ORDER BY market_date ROWS BETWEEN 1 FOLLOWING AND 4 FOLLOWING) AS next_4_highs,
        MIN(low) OVER (ORDER BY market_date ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS prev_4_lows,
        MIN(low) OVER (ORDER BY market_date ROWS BETWEEN 1 FOLLOWING AND 4 FOLLOWING) AS next_4_lows,
        
        -- FIX 2: Count the actual number of rows in the forward/backward windows
        COUNT(high) OVER (ORDER BY market_date ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS prev_count,
        COUNT(high) OVER (ORDER BY market_date ROWS BETWEEN 1 FOLLOWING AND 4 FOLLOWING) AS next_count
    FROM raw_data
),
identified_levels AS (
    -- FIX 3: Use UNION ALL instead of a CASE statement so that an "Outside Bar" 
    -- can correctly be flagged as BOTH a Resistance AND a Support level.
    SELECT 
        market_date,
        'Resistance' AS level_type,
        ROUND(CAST(high AS NUMERIC), 2) AS price_level,
        volume
    FROM swing_points
    WHERE high > prev_4_highs AND high > next_4_highs
      AND prev_count = 4 AND next_count = 4 -- Ensures the swing is confirmed and won't repaint
      
    UNION ALL
    
    SELECT 
        market_date,
        'Support' AS level_type,
        ROUND(CAST(low AS NUMERIC), 2) AS price_level,
        volume
    FROM swing_points
    WHERE low < prev_4_lows AND low < next_4_lows
      AND prev_count = 4 AND next_count = 4 -- Ensures the swing is confirmed and won't repaint
)
-- 4. Apply the strict 60-day visual cutoff AFTER all calculations are complete
SELECT * FROM identified_levels
WHERE market_date >= (
    SELECT MAX(market_date) - INTERVAL '60 days' 
    FROM daily_market_data 
    WHERE ticker = :ticker
)
ORDER BY 
    price_level DESC;
