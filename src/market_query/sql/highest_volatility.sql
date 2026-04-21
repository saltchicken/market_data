-- ============================================================================
-- Highest Volatility Stocks
--
-- Identifies the most volatile, highly-liquid stocks in the market.
-- Ideal for day traders or momentum traders looking for large intraday ranges.
-- 
-- Filters for:
-- 1. High Baseline Volatility (ATR % > 6%)
-- 2. Short-term volatility is not rapidly decreasing (5-Day vs 21-Day ATR > -15%)
-- 3. High Liquidity (> 1M shares/day average) to prevent slippage
-- ============================================================================

WITH latest_data AS (
  SELECT
    ticker,
    market_date,
    close,
    atr_14_pct,
    atr_5_21_dist_pct,
    atr_14_dod_pct,
    rvol_sma_60,
    vol_sma_60,
    volume_dod_pct,
    gap_pct
  FROM daily_indicators
  WHERE market_date = (SELECT MAX(market_date) FROM daily_indicators)
)

SELECT
  ticker,
  market_date,
  ROUND(CAST(close AS NUMERIC), 2) AS close,
  ROUND(CAST(atr_14_pct AS NUMERIC), 2) AS atr_14_pct,
  ROUND(CAST(atr_5_21_dist_pct AS NUMERIC), 2) AS volatility_expansion_pct,

  -- Create a composite score to rank by: Base ATR + 10% of the expansion factor.
  -- This boosts stocks with expanding volatility without dropping those undergoing a slight pullback.
  ROUND(
    CAST(atr_14_pct + (COALESCE(atr_5_21_dist_pct, 0) * 0.1) AS NUMERIC), 2
  ) AS composite_volatility_score,

  ROUND(CAST(atr_14_dod_pct AS NUMERIC), 2) AS atr_dod_pct,
  ROUND(CAST(rvol_sma_60 AS NUMERIC), 2) AS rvol_60d,
  ROUND(CAST(vol_sma_60 AS NUMERIC), 0) AS avg_volume_60d,

  -- Watchlist Integration: Set a target volume of 1.5x the average 30-minute volume
  -- (Assuming 6.5 hours or 13 x 30-min periods in a standard trading day)
  ROUND(CAST((vol_sma_60 / 13.0) * 1.5 AS NUMERIC), 0) AS target_volume

FROM latest_data
WHERE
  close >= 1.0                        -- Exclude penny stocks (less than $1)
  AND vol_sma_60 >= 1000000           -- Must trade > 1M shares/day on average
  AND atr_14_pct >= 6.0               -- Minimum 6% daily true range
  -- Short-term volatility is not rapidly decreasing
  AND atr_5_21_dist_pct > -15.0
ORDER BY composite_volatility_score DESC
LIMIT 50;
