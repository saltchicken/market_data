-- ============================================================================
-- Pullback in Uptrend (with Dynamic Horizontal Target Levels)
-- ============================================================================

WITH strategy_candidates AS (
  -- 1. Identify the core candidates that meet the strategy criteria
  SELECT
    ticker,
    market_date,
    close,
    vol_sma_60,
    sma_50_dist_pct,
    sma_200_dist_pct,
    atr_14_pct,
    atr_14,
    atr_5,
    vol_5_21_dist_pct,
    rvol_sma_60,
    close_slope_21d,
    close_r2_21d,
    sma_21,
    close_slope_3d,
    close_r2_3d
  FROM daily_indicators
  WHERE
    market_date = (SELECT MAX(market_date) FROM daily_indicators)
    AND close > 1.0
    AND atr_14_pct > 5.0 AND atr_14_pct < 20.0
    AND rvol_sma_60 > 1.5
    AND close_slope_21d > 0 AND close_r2_21d > 0.5
    AND close_slope_3d < 0 AND close_r2_3d > 0.5
    AND atr_14_pct IS NOT NULL AND rvol_sma_60 IS NOT NULL
),

recent_data AS (
  -- 2. Pull the last 80 days of raw price data ONLY for our candidate tickers to find swings
  SELECT
    d.ticker,
    d.market_date,
    d.high,
    d.low,
    MAX(d.high)
      OVER (
        PARTITION BY d.ticker
        ORDER BY d.market_date ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
      )
      AS prev_4_highs,
    MAX(d.high)
      OVER (
        PARTITION BY d.ticker
        ORDER BY d.market_date ROWS BETWEEN 1 FOLLOWING AND 4 FOLLOWING
      )
      AS next_4_highs,
    MIN(d.low)
      OVER (
        PARTITION BY d.ticker
        ORDER BY d.market_date ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
      )
      AS prev_4_lows,
    MIN(d.low)
      OVER (
        PARTITION BY d.ticker
        ORDER BY d.market_date ROWS BETWEEN 1 FOLLOWING AND 4 FOLLOWING
      )
      AS next_4_lows,
    COUNT(d.high)
      OVER (
        PARTITION BY d.ticker
        ORDER BY d.market_date ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
      )
      AS prev_count,
    COUNT(d.high)
      OVER (
        PARTITION BY d.ticker
        ORDER BY d.market_date ROWS BETWEEN 1 FOLLOWING AND 4 FOLLOWING
      )
      AS next_count
  FROM daily_market_data AS d
  INNER JOIN strategy_candidates AS c ON d.ticker = c.ticker
  WHERE
    d.market_date
    >= (SELECT MAX(market_date) - INTERVAL '80 days' FROM daily_market_data)
),

swing_levels AS (
  -- 3. Identify Support (Troughs) and Resistance (Peaks)
  SELECT
    ticker,
    'Resistance' AS level_type,
    high AS price_level
  FROM recent_data
  WHERE
    high > prev_4_highs
    AND high > next_4_highs
    AND prev_count = 4
    AND next_count = 4
  UNION ALL
  SELECT
    ticker,
    'Support' AS level_type,
    low AS price_level
  FROM recent_data
  WHERE
    low < prev_4_lows
    AND low < next_4_lows
    AND prev_count = 4
    AND next_count = 4
),

closest_levels AS (
  -- 4. Calculate the distance to every level and rank the closest ones
  SELECT
    c.ticker,
    s.level_type,
    s.price_level,
    ROW_NUMBER() OVER (
      PARTITION BY c.ticker, s.level_type
      ORDER BY ABS(c.close - s.price_level) ASC
    ) AS rank
  FROM strategy_candidates AS c
  INNER JOIN swing_levels AS s ON c.ticker = s.ticker
  WHERE
    (s.level_type = 'Resistance' AND s.price_level > c.close)
    OR (s.level_type = 'Support' AND s.price_level < c.close)
),

pivoted_levels AS (
  -- 5. Flatten the closest support and resistance into single rows per ticker
  SELECT
    ticker,
    MAX(CASE WHEN level_type = 'Support' THEN price_level END)
      AS nearest_support,
    MAX(CASE WHEN level_type = 'Resistance' THEN price_level END)
      AS nearest_resistance
  FROM closest_levels
  WHERE rank = 1
  GROUP BY ticker
)

-- 6. Output the final strategy logic merged with our horizontal targets
SELECT
  c.ticker,
  c.market_date,
  c.close,

  -- Target Limits: Use horizontal levels if found, otherwise fallback to the fixed percentage formula
  c.sma_50_dist_pct,
  c.sma_200_dist_pct,

  -- TARGET VOLUME: 200% of average volume per 30-min bar
  c.atr_14,

  c.atr_5,
  c.rvol_sma_60,
  c.close_slope_21d,
  c.close_r2_21d,
  c.close_slope_3d,
  c.close_r2_3d,
  ROUND(CAST(COALESCE(p.nearest_support, c.close * 0.98) AS NUMERIC), 2)
    AS target_buy,
  ROUND(CAST(COALESCE(p.nearest_resistance, c.close * 1.05) AS NUMERIC), 2)
    AS target_sell,
  ROUND(CAST((c.vol_sma_60 / 13.0) * 2.0 AS NUMERIC), 0) AS target_volume,
  ROUND(CAST(c.atr_14_pct AS NUMERIC), 2) AS atr_14_pct,
  ROUND(CAST(c.vol_5_21_dist_pct AS NUMERIC), 2) AS vol_5_21_dist_pct,
  (c.close_slope_21d * 21) / c.sma_21 AS close_slope_normalized

FROM strategy_candidates AS c
LEFT JOIN pivoted_levels AS p ON c.ticker = p.ticker
ORDER BY c.atr_14_pct DESC
LIMIT 30;
