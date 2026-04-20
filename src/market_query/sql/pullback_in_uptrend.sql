SELECT
  ticker,
  market_date,
  close,
  
  -- Target Limit Orders automatically picked up by market_query mapping
  ROUND(CAST(close * 0.98 AS NUMERIC), 2) AS target_buy,
  ROUND(CAST(close * 1.05 AS NUMERIC), 2) AS target_sell,

    -- TARGET VOLUME: 
  -- 1. Take the 60-day average daily volume (vol_sma_60)
  -- 2. Divide by 13 (number of 30-min periods in a trading day) to get average volume per 30-min bar
  -- 3. Multiply by 2.0 to trigger an alert only when a 30-min bar sees 200% of average volume
  ROUND(CAST((vol_sma_60 / 13.0) * 2.0 AS NUMERIC), 0) AS target_volume,

  sma_50_dist_pct,
  sma_200_dist_pct,
  ROUND(CAST(atr_14_pct AS NUMERIC), 2) AS atr_14_pct,
  atr_14,
  atr_5,
  ROUND(CAST(vol_5_21_dist_pct AS NUMERIC), 2) AS vol_5_21_dist_pct,
  rvol_sma_60,
  close_slope_21d,
  close_r2_21d,
  (close_slope_21d * 21) / sma_21 AS close_slope_normalized,
  close_slope_3d,
  close_r2_3d

FROM
  daily_indicators
WHERE market_date = (SELECT MAX(market_date) FROM daily_indicators)
AND close > 1.0

AND atr_14_pct > 5.0 AND atr_14_pct < 20.0

AND rvol_sma_60 > 1.5

AND close_slope_21d > 0
AND close_r2_21d > 0.5

AND close_slope_3d < 0
AND close_r2_3d > 0.5

AND atr_14_pct IS NOT NULL
AND rvol_sma_60 IS NOT NULL

-- AND sma_50 > sma_200
ORDER BY
  atr_14_pct DESC
LIMIT 30
