-- ============================================================================
-- Financial Fortress Screener (Low Debt & High Solvency)
--
-- Identifies companies with bulletproof balance sheets (low debt-to-equity, 
-- high current/quick ratios) that are also profitable and in a macro uptrend.
-- ============================================================================

WITH latest_technicals AS (
  -- Grab the most recent technical indicators
  SELECT * FROM daily_indicators
  WHERE market_date = (SELECT MAX(market_date) FROM daily_indicators)
),

latest_fundamentals AS (
  -- Grab the most recent Finviz screener data
  SELECT * FROM finviz_screener
  WHERE date = (SELECT MAX(date) FROM finviz_screener)
)

SELECT
  t.ticker,
  f.company,
  f.sector,
  ROUND(CAST(f.debt_eq AS NUMERIC), 2) AS debt_eq,
  ROUND(CAST(f.curr_r AS NUMERIC), 2) AS current_ratio,
  ROUND(CAST(f.quick_r AS NUMERIC), 2) AS quick_ratio,
  ROUND(CAST(f.p_e AS NUMERIC), 2) AS p_e,
  ROUND(CAST(t.close AS NUMERIC), 2) AS close,
  ROUND(CAST(t.sma_200_dist_pct AS NUMERIC), 2) AS dist_from_200d_pct
FROM latest_technicals AS t
INNER JOIN latest_fundamentals AS f ON t.ticker = f.ticker
WHERE
  -- 1. Strict Solvency & Liquidity (The "Interest Coverage" Proxies)
  f.curr_r >= 2.0           -- Extremely safe short-term liquidity (Assets are 2x liabilities)
  AND f.quick_r >= 1.0      -- Can cover immediate liabilities without needing to sell inventory

  -- 2. Strict Debt Load (The "Debt-to-Earnings" Proxies)
  AND f.debt_eq <= 0.5      -- Total debt is half or less of shareholder equity
  AND (f.ltdebt_eq IS NULL OR f.ltdebt_eq <= 0.5) -- Long-term debt is also low

  -- 3. Basic Viability & Profitability
  AND f.market_cap > 500000000  -- Exclude micro-caps (>$500M minimum)
  AND f.p_e > 0                 -- Must be profitable (Earnings > 0)
  AND f.p_e < 25                -- Avoid heavily overvalued hype stocks

  -- 4. Technical Baseline
  AND t.close >= 1.0            -- Avoid penny stocks
  AND t.close > t.sma_200       -- Only buy companies in a long-term macro uptrend

-- Rank them by lowest debt burden first, then highest liquidity
ORDER BY f.debt_eq ASC, f.curr_r DESC
LIMIT 50;
