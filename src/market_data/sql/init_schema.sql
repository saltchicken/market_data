DROP TABLE IF EXISTS daily_market_data CASCADE;
DROP TABLE IF EXISTS daily_indicators CASCADE;

CREATE TABLE daily_market_data (
    ticker TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    market_date DATE NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    vwap DOUBLE PRECISION,
    timestamp BIGINT,
    transactions DOUBLE PRECISION,
    datetime TIMESTAMP WITHOUT TIME ZONE,

    CONSTRAINT pk_ticker_date PRIMARY KEY (ticker, market_date)
);

CREATE TABLE daily_indicators (
    ticker TEXT NOT NULL,
    market_date DATE NOT NULL,
    
    -- Price & Trend Indicators
    close DOUBLE PRECISION,
    prev_close DOUBLE PRECISION,
    gap_pct DOUBLE PRECISION,
    price_change_dod_pct DOUBLE PRECISION,
    price_change_wow_pct DOUBLE PRECISION,
    price_change_mom_pct DOUBLE PRECISION,
    open_to_close_pct DOUBLE PRECISION,
    atr_14 DOUBLE PRECISION,
    atr_14_pct DOUBLE PRECISION,
    atr_5 DOUBLE PRECISION,
    atr_21 DOUBLE PRECISION,
    atr_5_21_dist_pct DOUBLE PRECISION,
    sma_21 DOUBLE PRECISION,
    sma_21_dist_pct DOUBLE PRECISION,
    sma_50 DOUBLE PRECISION,
    sma_50_dist_pct DOUBLE PRECISION,
    sma_200 DOUBLE PRECISION,
    sma_200_dist_pct DOUBLE PRECISION,
    ema_9 DOUBLE PRECISION,
    ema_21 DOUBLE PRECISION,
    ema_9_21_dist_pct DOUBLE PRECISION,
    
    -- Bollinger Bands
    bb_mid DOUBLE PRECISION,
    bb_upper DOUBLE PRECISION,
    bb_lower DOUBLE PRECISION,
    
    -- Keltner Channels
    kc_mid DOUBLE PRECISION,
    kc_upper DOUBLE PRECISION,
    kc_lower DOUBLE PRECISION,

    -- Oscillators & Momentum
    rsi_14 DOUBLE PRECISION,
    rsi_5 DOUBLE PRECISION,
    rsi_21 DOUBLE PRECISION,
    rsi_5_21_diff DOUBLE PRECISION,
    macd DOUBLE PRECISION,
    macd_signal DOUBLE PRECISION,
    macd_hist DOUBLE PRECISION,
    
    -- Trend Strength (ADX) & Cumulative Volume (OBV)
    adx_14 DOUBLE PRECISION,
    plus_di DOUBLE PRECISION,
    minus_di DOUBLE PRECISION,
    obv DOUBLE PRECISION,

    -- Volume Baselines (The Denominators)
    vol_ema_5 DOUBLE PRECISION,
    vol_sma_10 DOUBLE PRECISION,
    vol_ema_21 DOUBLE PRECISION,
    vol_sma_60 DOUBLE PRECISION,
    vol_5_21_dist_pct DOUBLE PRECISION,

    -- Relative Volume (RVOL) Metrics
    rvol_ema_5 DOUBLE PRECISION,
    rvol_sma_10 DOUBLE PRECISION,
    rvol_ema_21 DOUBLE PRECISION,
    rvol_sma_60 DOUBLE PRECISION,
    
    -- Day-Over-Day (DoD), WoW, and MoM Rate of Change Metrics
    rvol_ema_5_dod_diff DOUBLE PRECISION,
    volume_dod_pct DOUBLE PRECISION,
    volume_wow_pct DOUBLE PRECISION,
    volume_mom_pct DOUBLE PRECISION,
    rsi_14_dod_diff DOUBLE PRECISION,
    macd_hist_dod_diff DOUBLE PRECISION,
    atr_14_dod_pct DOUBLE PRECISION,

    -- Smoothed Velocity Metrics
    volume_dod_sma_3 DOUBLE PRECISION,
    rsi_velocity_3d DOUBLE PRECISION,

    -- Trend Trajectory & Confidence (Slopes & R-Squared)
    close_slope_3d DOUBLE PRECISION,
    close_r2_3d DOUBLE PRECISION,
    close_slope_5d DOUBLE PRECISION,
    close_r2_5d DOUBLE PRECISION,
    close_slope_10d DOUBLE PRECISION,
    close_r2_10d DOUBLE PRECISION,
    close_slope_21d DOUBLE PRECISION,
    close_r2_21d DOUBLE PRECISION,
    
    rsi_14_slope_3d DOUBLE PRECISION,
    rsi_14_r2_3d DOUBLE PRECISION,
    rsi_14_slope_5d DOUBLE PRECISION,
    rsi_14_r2_5d DOUBLE PRECISION,
    rsi_14_slope_10d DOUBLE PRECISION,
    rsi_14_r2_10d DOUBLE PRECISION,
    rsi_14_slope_21d DOUBLE PRECISION,
    rsi_14_r2_21d DOUBLE PRECISION,

    -- Advanced Trajectory Metrics (Percentage Normalized)
    sma_50_dist_pct_slope_3d DOUBLE PRECISION,
    sma_50_dist_pct_r2_3d DOUBLE PRECISION,
    sma_50_dist_pct_slope_5d DOUBLE PRECISION,
    sma_50_dist_pct_r2_5d DOUBLE PRECISION,
    sma_50_dist_pct_slope_10d DOUBLE PRECISION,
    sma_50_dist_pct_r2_10d DOUBLE PRECISION,
    sma_50_dist_pct_slope_21d DOUBLE PRECISION,
    sma_50_dist_pct_r2_21d DOUBLE PRECISION,

    CONSTRAINT pk_ticker_indicator_date PRIMARY KEY (ticker, market_date)
);

-- Indexes to drastically speed up Pandas pulling historical chunks
CREATE INDEX idx_daily_market_data_date ON daily_market_data(market_date);
CREATE INDEX idx_daily_market_data_ticker ON daily_market_data(ticker);


-- ============================================================================
-- DATA DICTIONARY & ANNOTATIONS
-- ============================================================================

-- Tables
COMMENT ON TABLE daily_market_data IS 'Raw OHLCV daily market data fetched directly from Polygon.';
COMMENT ON TABLE daily_indicators IS 'Calculated technical indicators, volatility, momentum, and relative volume metrics.';

-- daily_market_data Columns
COMMENT ON COLUMN daily_market_data.ticker IS 'The stock ticker symbol (e.g., AAPL).';
COMMENT ON COLUMN daily_market_data.market_date IS 'The trading date.';
COMMENT ON COLUMN daily_market_data.open IS 'The opening price of the asset.';
COMMENT ON COLUMN daily_market_data.high IS 'The highest price reached during the trading day.';
COMMENT ON COLUMN daily_market_data.low IS 'The lowest price reached during the trading day.';
COMMENT ON COLUMN daily_market_data.close IS 'The closing price of the asset.';
COMMENT ON COLUMN daily_market_data.volume IS 'The total number of shares traded during the day.';
COMMENT ON COLUMN daily_market_data.vwap IS 'Volume Weighted Average Price for the day.';
COMMENT ON COLUMN daily_market_data.timestamp IS 'Polygon API Unix timestamp.';
COMMENT ON COLUMN daily_market_data.transactions IS 'Number of individual trades executed during the day.';
COMMENT ON COLUMN daily_market_data.datetime IS 'Human-readable timestamp converted from Polygon unix timestamp.';

-- daily_indicators Columns: Identifiers & Price
COMMENT ON COLUMN daily_indicators.ticker IS 'The stock ticker symbol.';
COMMENT ON COLUMN daily_indicators.market_date IS 'The trading date.';
COMMENT ON COLUMN daily_indicators.close IS 'The daily closing price.';
COMMENT ON COLUMN daily_indicators.prev_close IS 'The previous trading day''s closing price.';

-- daily_indicators Columns: Price Change %
COMMENT ON COLUMN daily_indicators.gap_pct IS 'Percentage difference between today''s open and yesterday''s close.';
COMMENT ON COLUMN daily_indicators.price_change_dod_pct IS 'Day-over-Day percentage change (Today''s Close vs Yesterday''s Close).';
COMMENT ON COLUMN daily_indicators.price_change_wow_pct IS 'Week-over-Week percentage change (Today''s Close vs 5 trading days ago).';
COMMENT ON COLUMN daily_indicators.price_change_mom_pct IS 'Month-over-Month percentage change (Today''s Close vs 21 trading days ago).';
COMMENT ON COLUMN daily_indicators.open_to_close_pct IS 'Intraday performance: Percentage change from today''s open to today''s close.';

-- daily_indicators Columns: Volatility (ATR)
COMMENT ON COLUMN daily_indicators.atr_14 IS '14-Day Average True Range (Absolute volatility measure).';
COMMENT ON COLUMN daily_indicators.atr_14_pct IS '14-Day ATR normalized as a percentage of the closing price.';
COMMENT ON COLUMN daily_indicators.atr_5 IS '5-Day Average True Range (Short-term volatility).';
COMMENT ON COLUMN daily_indicators.atr_21 IS '21-Day Average True Range (Medium-term volatility).';
COMMENT ON COLUMN daily_indicators.atr_5_21_dist_pct IS 'Percentage difference between 5-Day ATR and 21-Day ATR (Measures volatility expansion).';

-- daily_indicators Columns: Moving Averages (SMA & EMA)
COMMENT ON COLUMN daily_indicators.sma_21 IS '21-Day Simple Moving Average.';
COMMENT ON COLUMN daily_indicators.sma_21_dist_pct IS 'Percentage distance of current price from the 21-Day SMA.';
COMMENT ON COLUMN daily_indicators.sma_50 IS '50-Day Simple Moving Average.';
COMMENT ON COLUMN daily_indicators.sma_50_dist_pct IS 'Percentage distance of current price from the 50-Day SMA.';
COMMENT ON COLUMN daily_indicators.sma_200 IS '200-Day Simple Moving Average.';
COMMENT ON COLUMN daily_indicators.sma_200_dist_pct IS 'Percentage distance of current price from the 200-Day SMA.';
COMMENT ON COLUMN daily_indicators.ema_9 IS '9-Day Exponential Moving Average.';
COMMENT ON COLUMN daily_indicators.ema_21 IS '21-Day Exponential Moving Average.';
COMMENT ON COLUMN daily_indicators.ema_9_21_dist_pct IS 'Percentage distance between the 9-Day EMA and 21-Day EMA.';

-- daily_indicators Columns: Bands & Channels
COMMENT ON COLUMN daily_indicators.bb_mid IS 'Bollinger Bands Middle Line (20-Day SMA).';
COMMENT ON COLUMN daily_indicators.bb_upper IS 'Bollinger Bands Upper Line (+2 Standard Deviations).';
COMMENT ON COLUMN daily_indicators.bb_lower IS 'Bollinger Bands Lower Line (-2 Standard Deviations).';
COMMENT ON COLUMN daily_indicators.kc_mid IS 'Keltner Channel Middle Line (20-Day EMA).';
COMMENT ON COLUMN daily_indicators.kc_upper IS 'Keltner Channel Upper Line (+2 10-Day ATRs).';
COMMENT ON COLUMN daily_indicators.kc_lower IS 'Keltner Channel Lower Line (-2 10-Day ATRs).';

-- daily_indicators Columns: Momentum (RSI & MACD)
COMMENT ON COLUMN daily_indicators.rsi_14 IS '14-Day Relative Strength Index (Standard Momentum).';
COMMENT ON COLUMN daily_indicators.rsi_5 IS '5-Day Relative Strength Index (Fast Momentum).';
COMMENT ON COLUMN daily_indicators.rsi_21 IS '21-Day Relative Strength Index (Smoothed Momentum).';
COMMENT ON COLUMN daily_indicators.rsi_5_21_diff IS 'Absolute difference between 5-Day RSI and 21-Day RSI.';
COMMENT ON COLUMN daily_indicators.macd IS 'Moving Average Convergence Divergence (12-Day EMA - 26-Day EMA).';
COMMENT ON COLUMN daily_indicators.macd_signal IS 'MACD Signal Line (9-Day EMA of MACD).';
COMMENT ON COLUMN daily_indicators.macd_hist IS 'MACD Histogram (MACD - Signal Line).';

-- daily_indicators Columns: Trend Strength (ADX & OBV)
COMMENT ON COLUMN daily_indicators.adx_14 IS '14-Day Average Directional Index (Trend strength).';
COMMENT ON COLUMN daily_indicators.plus_di IS 'Positive Directional Indicator (+DI).';
COMMENT ON COLUMN daily_indicators.minus_di IS 'Negative Directional Indicator (-DI).';
COMMENT ON COLUMN daily_indicators.obv IS 'On-Balance Volume (Cumulative volume added on up days, subtracted on down days).';

-- daily_indicators Columns: Volume Baselines
COMMENT ON COLUMN daily_indicators.vol_ema_5 IS '5-Day Exponential Moving Average of Volume.';
COMMENT ON COLUMN daily_indicators.vol_sma_10 IS '10-Day Simple Moving Average of Volume.';
COMMENT ON COLUMN daily_indicators.vol_ema_21 IS '21-Day Exponential Moving Average of Volume.';
COMMENT ON COLUMN daily_indicators.vol_sma_60 IS '60-Day Simple Moving Average of Volume.';
COMMENT ON COLUMN daily_indicators.vol_5_21_dist_pct IS 'Percentage difference between 5-Day Volume EMA and 21-Day Volume EMA.';

-- daily_indicators Columns: Relative Volume (RVOL)
COMMENT ON COLUMN daily_indicators.rvol_ema_5 IS 'Relative Volume: Today''s volume divided by the 5-Day EMA Volume.';
COMMENT ON COLUMN daily_indicators.rvol_sma_10 IS 'Relative Volume: Today''s volume divided by the 10-Day SMA Volume.';
COMMENT ON COLUMN daily_indicators.rvol_ema_21 IS 'Relative Volume: Today''s volume divided by the 21-Day EMA Volume.';
COMMENT ON COLUMN daily_indicators.rvol_sma_60 IS 'Relative Volume: Today''s volume divided by the 60-Day SMA Volume.';

-- daily_indicators Columns: Rate of Change (DoD) Metrics
COMMENT ON COLUMN daily_indicators.rvol_ema_5_dod_diff IS 'Day-over-Day difference in 5-Day RVOL.';
COMMENT ON COLUMN daily_indicators.volume_dod_pct IS 'Day-over-Day percentage change in raw trading volume.';
COMMENT ON COLUMN daily_indicators.volume_wow_pct IS 'Week-over-Week percentage change in raw trading volume.';
COMMENT ON COLUMN daily_indicators.volume_mom_pct IS 'Month-over-Month percentage change in raw trading volume.';
COMMENT ON COLUMN daily_indicators.rsi_14_dod_diff IS 'Day-over-Day absolute difference in 14-Day RSI.';
COMMENT ON COLUMN daily_indicators.macd_hist_dod_diff IS 'Day-over-Day absolute difference in the MACD Histogram.';
COMMENT ON COLUMN daily_indicators.atr_14_dod_pct IS 'Day-over-Day percentage change in 14-Day ATR.';

-- daily_indicators Columns: Smoothed Velocity Metrics
COMMENT ON COLUMN daily_indicators.volume_dod_sma_3 IS '3-Day Simple Moving Average of the Day-over-Day volume percentage change.';
COMMENT ON COLUMN daily_indicators.rsi_velocity_3d IS '3-Day Simple Moving Average of the Day-over-Day RSI difference.';

-- daily_indicators Columns: Trend Trajectories (Close Slopes & R-Squared)
COMMENT ON COLUMN daily_indicators.close_slope_3d IS 'Linear regression slope of the closing price over 3 days.';
COMMENT ON COLUMN daily_indicators.close_r2_3d IS 'R-Squared (confidence fit) of the 3-day closing price linear regression.';
COMMENT ON COLUMN daily_indicators.close_slope_5d IS 'Linear regression slope of the closing price over 5 days.';
COMMENT ON COLUMN daily_indicators.close_r2_5d IS 'R-Squared (confidence fit) of the 5-day closing price linear regression.';
COMMENT ON COLUMN daily_indicators.close_slope_10d IS 'Linear regression slope of the closing price over 10 days.';
COMMENT ON COLUMN daily_indicators.close_r2_10d IS 'R-Squared (confidence fit) of the 10-day closing price linear regression.';
COMMENT ON COLUMN daily_indicators.close_slope_21d IS 'Linear regression slope of the closing price over 21 days.';
COMMENT ON COLUMN daily_indicators.close_r2_21d IS 'R-Squared (confidence fit) of the 21-day closing price linear regression.';

-- daily_indicators Columns: Trend Trajectories (RSI Slopes & R-Squared)
COMMENT ON COLUMN daily_indicators.rsi_14_slope_3d IS 'Linear regression slope of the 14-Day RSI over 3 days.';
COMMENT ON COLUMN daily_indicators.rsi_14_r2_3d IS 'R-Squared fit of the 3-day RSI linear regression.';
COMMENT ON COLUMN daily_indicators.rsi_14_slope_5d IS 'Linear regression slope of the 14-Day RSI over 5 days.';
COMMENT ON COLUMN daily_indicators.rsi_14_r2_5d IS 'R-Squared fit of the 5-day RSI linear regression.';
COMMENT ON COLUMN daily_indicators.rsi_14_slope_10d IS 'Linear regression slope of the 14-Day RSI over 10 days.';
COMMENT ON COLUMN daily_indicators.rsi_14_r2_10d IS 'R-Squared fit of the 10-day RSI linear regression.';
COMMENT ON COLUMN daily_indicators.rsi_14_slope_21d IS 'Linear regression slope of the 14-Day RSI over 21 days.';
COMMENT ON COLUMN daily_indicators.rsi_14_r2_21d IS 'R-Squared fit of the 21-day RSI linear regression.';

-- daily_indicators Columns: Advanced Trajectories (SMA 50 Dist % Slopes & R-Squared)
COMMENT ON COLUMN daily_indicators.sma_50_dist_pct_slope_3d IS 'Linear regression slope of the price distance from 50-Day SMA over 3 days.';
COMMENT ON COLUMN daily_indicators.sma_50_dist_pct_r2_3d IS 'R-Squared fit of the 3-day SMA 50 distance regression.';
COMMENT ON COLUMN daily_indicators.sma_50_dist_pct_slope_5d IS 'Linear regression slope of the price distance from 50-Day SMA over 5 days.';
COMMENT ON COLUMN daily_indicators.sma_50_dist_pct_r2_5d IS 'R-Squared fit of the 5-day SMA 50 distance regression.';
COMMENT ON COLUMN daily_indicators.sma_50_dist_pct_slope_10d IS 'Linear regression slope of the price distance from 50-Day SMA over 10 days.';
COMMENT ON COLUMN daily_indicators.sma_50_dist_pct_r2_10d IS 'R-Squared fit of the 10-day SMA 50 distance regression.';
COMMENT ON COLUMN daily_indicators.sma_50_dist_pct_slope_21d IS 'Linear regression slope of the price distance from 50-Day SMA over 21 days.';
COMMENT ON COLUMN daily_indicators.sma_50_dist_pct_r2_21d IS 'R-Squared fit of the 21-day SMA 50 distance regression.';
