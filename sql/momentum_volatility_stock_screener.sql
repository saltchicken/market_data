WITH basemetrics AS (
  SELECT
    ticker,
    market_date,
    -- The original Relative Volume inputs
    rvol_ema_5,
    rvol_sma_10,
    rvol_ema_21,
    rvol_sma_60,

    -- The Base Volume Score (Original Formula)
    atr_14_pct,

    -- Trend Trajectory & Quality Metrics
    (
      (0.15 * COALESCE(rvol_ema_5, 0))
      + (0.15 * COALESCE(rvol_sma_10, 0))
      + (0.30 * COALESCE(rvol_ema_21, 0))
      + (0.40 * COALESCE(rvol_sma_60, 0))
    ) AS base_vol_score,
    COALESCE(close_r2_10d, 0) AS price_trend_r2,

    -- Volume Trend Metrics (Replacing removed OBV fields)
    COALESCE(close_slope_10d, 0) AS price_trend_slope,
    COALESCE(vol_5_21_dist_pct_r2_10d, 0) AS vol_trend_r2,

    -- Momentum & Velocity
    COALESCE(vol_5_21_dist_pct, 0) AS vol_dist_pct,
    COALESCE(rsi_14_slope_3d, 0) AS short_term_momentum,

    -- Volatility
    COALESCE(rsi_velocity_3d, 0) AS rsi_velocity
  FROM daily_indicators
  WHERE market_date = (SELECT MAX(market_date) FROM daily_indicators)
)

SELECT
  ticker,
  market_date,
  ROUND(CAST(atr_14_pct AS NUMERIC), 2) AS atr_14_pct,
  ROUND(CAST(base_vol_score AS NUMERIC), 2) AS base_vol_score,
  ROUND(CAST(price_trend_r2 AS NUMERIC), 2) AS price_trend_r2,
  ROUND(CAST(vol_trend_r2 AS NUMERIC), 2) AS vol_trend_r2,
  ROUND(CAST(short_term_momentum AS NUMERIC), 2) AS rsi_slope_3d,

  -- ==========================================
  -- THE ENHANCED DYNAMIC ATTENTION SCORE
  -- ==========================================
  -- 1. Base Score: Start with the weighted Relative Volume.
  -- 2. Price Quality Boost: Up to 50% multiplier IF the price is moving in a clean UPWARD trend 
  --    (We check slope > 0 so we don't accidentally reward a perfect downtrend).
  -- 3. Volume Quality Boost: Up to 30% multiplier if short-term volume surges are trending cleanly.
  -- 4. Momentum Kick: A small flat bonus if RSI and Velocity are actively accelerating.
  ROUND(CAST(
    (
      base_vol_score
      * (
        1.0
        + CASE WHEN price_trend_slope > 0 THEN (price_trend_r2 * 0.5) ELSE 0 END
      )
      * (1.0 + CASE WHEN vol_dist_pct > 0 THEN (vol_trend_r2 * 0.3) ELSE 0 END)
    )
    + GREATEST(0, short_term_momentum * 0.1)
    + GREATEST(0, rsi_velocity * 0.05)
    AS NUMERIC
  ), 2) AS enhanced_attention_score

FROM basemetrics
WHERE
  base_vol_score > 1.2  -- Minimum threshold: We want stocks with at least 20% above-average baseline volume
  AND atr_14_pct > 4.0      -- Minimum Volatility: We only care about stocks that actually move (4% is a healthy baseline)
ORDER BY enhanced_attention_score DESC
LIMIT 50;
