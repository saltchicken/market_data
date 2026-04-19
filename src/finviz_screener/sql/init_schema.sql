DROP TABLE IF EXISTS finviz_screener CASCADE;

CREATE TABLE finviz_screener (
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    company TEXT,
    sector TEXT,
    industry TEXT,
    country TEXT,
    
    -- Valuation
    market_cap DOUBLE PRECISION,
    p_e DOUBLE PRECISION,
    forward_p_e DOUBLE PRECISION,
    peg DOUBLE PRECISION,
    p_s DOUBLE PRECISION,
    p_b DOUBLE PRECISION,
    p_c DOUBLE PRECISION,
    p_fcf DOUBLE PRECISION,
    
    -- Financial
    dividend DOUBLE PRECISION,
    roa DOUBLE PRECISION,
    roe DOUBLE PRECISION,
    roic DOUBLE PRECISION,
    curr_r DOUBLE PRECISION,
    quick_r DOUBLE PRECISION,
    ltdebt_eq DOUBLE PRECISION,
    debt_eq DOUBLE PRECISION,
    gross_m DOUBLE PRECISION,
    oper_m DOUBLE PRECISION,
    profit_m DOUBLE PRECISION,
    earnings TEXT,
    eps_past_5y DOUBLE PRECISION,
    eps_next_5y DOUBLE PRECISION,
    sales_past_5y DOUBLE PRECISION,
    eps_this_y DOUBLE PRECISION,
    eps_next_y DOUBLE PRECISION,
    
    -- Ownership
    outstanding DOUBLE PRECISION,
    float DOUBLE PRECISION,
    insider_own DOUBLE PRECISION,
    insider_trans DOUBLE PRECISION,
    inst_own DOUBLE PRECISION,
    inst_trans DOUBLE PRECISION,
    short_float DOUBLE PRECISION,
    short_ratio DOUBLE PRECISION,

    -- Use composite primary key to enforce uniqueness per day per ticker
    CONSTRAINT pk_finviz_screener PRIMARY KEY (ticker, date)
);

-- Indexes for performance filtering
CREATE INDEX idx_finviz_screener_date ON finviz_screener(date);
CREATE INDEX idx_finviz_screener_ticker ON finviz_screener(ticker);
