WITH BaseMetrics AS (
    SELECT 
        ticker,
        market_date,
        -- The original Relative Volume inputs
        rvol_ema_5,
        rvol_sma_10,
        rvol_ema_21,
        rvol_sma_60,
        
        -- The Base Volume Score (Original Formula)
        (
            (0.15 * COALESCE(rvol_ema_5, 0)) +
            (0.15 * COALESCE(rvol_sma_10, 0)) +
            (0.30 * COALESCE(rvol_ema_21, 0)) +
            (0.40 * COALESCE(rvol_sma_60, 0))
        ) AS base_vol_score,
        
        -- Trend Trajectory & Quality Metrics
        COALESCE(close_r2_10d, 0) AS price_trend_r2,
        COALESCE(close_slope_10d, 0) AS price_trend_slope,
        
        -- Volume Trend Metrics (Replacing removed OBV fields)
        COALESCE(vol_5_21_dist_pct_r2_10d, 0) AS vol_trend_r2,
        COALESCE(vol_5_21_dist_pct, 0) AS vol_dist_pct,
        
        -- Momentum & Velocity
        COALESCE(rsi_14_slope_3d, 0) AS short_term_momentum,
        COALESCE(rsi_velocity_3d, 0) AS rsi_velocity,
        
        -- Volatility
        atr_14_pct
    FROM daily_indicators
    WHERE market_date = (SELECT MAX(market_date) FROM daily_indicators)
)
SELECT 
    bm.ticker,
    fd.name,
    fd.sector,
    fd.industry,
    bm.market_date,
    ROUND(CAST(bm.atr_14_pct AS NUMERIC), 2) AS atr_14_pct,
    ROUND(CAST(bm.base_vol_score AS NUMERIC), 2) AS base_vol_score,
    ROUND(CAST(bm.price_trend_r2 AS NUMERIC), 2) AS price_trend_r2,
    ROUND(CAST(bm.vol_trend_r2 AS NUMERIC), 2) AS vol_trend_r2,
    ROUND(CAST(bm.short_term_momentum AS NUMERIC), 2) AS rsi_slope_3d,
    
    -- ==========================================
    -- THE ENHANCED DYNAMIC ATTENTION SCORE
    -- ==========================================
    -- 1. Base Score: Start with the weighted Relative Volume.
    -- 2. Price Quality Boost: Up to 50% multiplier IF the price is moving in a clean UPWARD trend 
    --    (We check slope > 0 so we don't accidentally reward a perfect downtrend).
    -- 3. Volume Quality Boost: Up to 30% multiplier if short-term volume surges are trending cleanly.
    -- 4. Momentum Kick: A small flat bonus if RSI and Velocity are actively accelerating.
    ROUND(CAST(
        (bm.base_vol_score 
         * (1.0 + CASE WHEN bm.price_trend_slope > 0 THEN (bm.price_trend_r2 * 0.5) ELSE 0 END) 
         * (1.0 + CASE WHEN bm.vol_dist_pct > 0 THEN (bm.vol_trend_r2 * 0.3) ELSE 0 END)) 
         + GREATEST(0, bm.short_term_momentum * 0.1) 
         + GREATEST(0, bm.rsi_velocity * 0.05)
    AS NUMERIC), 2) AS enhanced_attention_score

FROM BaseMetrics bm
LEFT JOIN financedatabase fd 
    ON bm.ticker = fd.ticker
WHERE bm.base_vol_score > 1.2  -- Minimum threshold: We want stocks with at least 20% above-average baseline volume
  AND fd.country = 'United States'
  AND bm.atr_14_pct > 4.0      -- Minimum Volatility: We only care about stocks that actually move (4% is a healthy baseline)
  -- AND fd.sector = 'Energy'  -- (Commented out so it scans the whole market instead of restricting to one sector)
ORDER BY enhanced_attention_score DESC
LIMIT 50;
