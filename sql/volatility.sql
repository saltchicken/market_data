select
  ticker,
  market_date,
  close,
  atr_14_pct,
  ROUND(close::numeric - atr_14::numeric / 4, 2) AS buy_limit,
  ROUND(close::numeric + atr_14::numeric / 4, 2) AS sell_limit
from
  daily_indicators
where
  market_date = (SELECT MAX(market_date) FROM daily_indicators)
  AND ticker = :ticker
