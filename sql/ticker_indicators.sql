SELECT
  ticker,
  market_date,
  close,
  ROUND(CAST(atr_14_pct AS NUMERIC), 2) AS atr_14_pct,
  atr_14,
  atr_5,
  ROUND(CAST(vol_5_21_dist_pct AS NUMERIC), 2) AS vol_5_21_dist_pct,
  rvol_sma_60,
  close_slope_21d,
  close_r2_21d,
  close_slope_21d / close * 21 AS close_slope_normalized
FROM
  daily_indicators
WHERE market_date = (SELECT MAX(market_date) FROM daily_indicators)
AND close > 1.0

AND atr_14_pct > 5.0 AND atr_14_pct < 20.0

AND rvol_sma_60 > 1.5

AND close_slope_21d > 0
AND close_r2_21d > 0.5

AND atr_14_pct IS NOT NULL
AND rvol_sma_60 IS NOT NULL
ORDER BY
  atr_14_pct DESC
LIMIT 30
