-- ============================================================================
-- Fundamental Health Rating (0 - 100 Score)
--
-- Calculates a health score based on finviz_screener data.
-- Companies scoring > 50 are fundamentally profitable and healthy.
-- Companies scoring < 50 are generally unprofitable or heavily indebted.
-- ============================================================================

WITH latest_fundamentals AS (
    -- Get the most recent fundamental pull
    SELECT * FROM finviz_screener
    WHERE date = (SELECT MAX(date) FROM finviz_screener)
),

latest_technicals AS (
    -- Join with technicals to get current price and volume
    SELECT ticker, close
    FROM daily_indicators
    WHERE market_date = (SELECT MAX(market_date) FROM daily_indicators)
),

scored_companies AS (
    SELECT
        f.ticker,
        f.company,
        f.sector,
        t.close,
        f.profit_m,
        f.p_e,
        f.roe,
        f.roa,
        f.debt_eq,
        f.curr_r,
        f.eps_next_5y,
        
        -- ==========================================
        -- 100-POINT SCORING ALGORITHM
        -- ==========================================
        (
            -- 1. Profit Margin (Max 25 points)
            CASE
                WHEN f.profit_m > 20 THEN 25
                WHEN f.profit_m > 10 THEN 20
                WHEN f.profit_m > 0 THEN 15
                ELSE 0 
            END +
            
            -- 2. Return on Equity - ROE (Max 15 points)
            CASE
                WHEN f.roe > 15 THEN 15
                WHEN f.roe > 0 THEN 10
                ELSE 0 
            END +
            
            -- 3. Return on Assets - ROA (Max 10 points)
            CASE
                WHEN f.roa > 5 THEN 10
                WHEN f.roa > 0 THEN 5
                ELSE 0 
            END +
            
            -- 4. Valuation / P/E Ratio (Max 15 points)
            -- Negative P/E means they are losing money, so they get 0.
            CASE
                WHEN f.p_e > 0 AND f.p_e <= 20 THEN 15
                WHEN f.p_e > 20 AND f.p_e <= 35 THEN 10
                ELSE 0 
            END +
            
            -- 5. Future Growth (Max 15 points)
            CASE
                WHEN f.eps_next_5y > 10 THEN 15
                WHEN f.eps_next_5y > 0 THEN 10
                ELSE 0 
            END +
            
            -- 6. Debt Management (Max 10 points)
            CASE
                WHEN f.debt_eq < 0.5 THEN 10
                WHEN f.debt_eq < 1.0 THEN 5
                ELSE 0 
            END +
            
            -- 7. Liquidity / Current Ratio (Max 10 points)
            CASE
                WHEN f.curr_r > 1.5 THEN 10
                WHEN f.curr_r > 1.0 THEN 5
                ELSE 0 
            END
            
        ) AS fundamental_score

    FROM latest_fundamentals f
    LEFT JOIN latest_technicals t ON f.ticker = t.ticker
    WHERE
        -- Exclude companies with missing (NaN/NULL) fundamental data
        f.profit_m IS NOT NULL
        AND f.p_e IS NOT NULL
        AND f.roe IS NOT NULL
        AND f.roa IS NOT NULL
        AND f.debt_eq IS NOT NULL
        AND f.curr_r IS NOT NULL
        AND f.eps_next_5y IS NOT NULL
)

SELECT
    ticker,
    company,
    sector,
    fundamental_score,
    ROUND(CAST(close AS NUMERIC), 2) AS close,
    ROUND(CAST(profit_m AS NUMERIC), 2) AS profit_m_pct,
    ROUND(CAST(p_e AS NUMERIC), 2) AS p_e,
    ROUND(CAST(roe AS NUMERIC), 2) AS roe_pct,
    ROUND(CAST(debt_eq AS NUMERIC), 2) AS debt_to_equity,
    ROUND(CAST(eps_next_5y AS NUMERIC), 2) AS expected_growth_pct
FROM scored_companies
ORDER BY 
    fundamental_score DESC, 
    profit_m_pct DESC
LIMIT 50;
