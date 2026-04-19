-- ============================================================================
-- Value + Momentum Breakout
--
-- Looks for fundamentally undervalued companies (P/E < 20, positive ROE)
-- that are exhibiting strong recent technical momentum and high relative volume.
-- ============================================================================

WITH latest_technicals AS (
    SELECT * FROM daily_indicators 
    WHERE market_date = (SELECT MAX(market_date) FROM daily_indicators)
),
latest_fundamentals AS (
    SELECT * FROM finviz_screener 
    WHERE date = (SELECT MAX(date) FROM finviz_screener)
)
SELECT 
    t.ticker,
    f.company,
    f.sector,
    ROUND(t.close::numeric, 2) AS close,
    ROUND(t.volume_dod_pct::numeric, 2) AS vol_surge_pct,
    ROUND(t.rsi_14::numeric, 2) AS rsi,
    f.p_e,
    f.roe
FROM latest_technicals t
JOIN latest_fundamentals f ON t.ticker = f.ticker
WHERE 
    -- 1. Fundamental Value Filters
    f.p_e BETWEEN 5 AND 20          -- Profitable but not overvalued
    AND f.roe > 0                   -- Positive Return on Equity
    AND f.market_cap > 500000000    -- Micro-cap filter (>$500M)
    
    -- 2. Technical Momentum Filters
    AND t.close >= 5.0              -- No penny stocks
    AND t.close > t.sma_50          -- In a medium-term uptrend
    AND t.rsi_14 BETWEEN 55 AND 70  -- Strong momentum, but not wildly overbought
    AND t.volume_dod_pct > 50       -- Volume surged by >50% yesterday
    
ORDER BY t.volume_dod_pct DESC;
