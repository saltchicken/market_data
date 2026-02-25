import numpy as np
from data import fetch_historical_data
from indicators import calculate_indicators


def get_latest_live_signal(df, symbol, config):
    if df is None or df.empty:
        return None

    latest_data = df.iloc[-1]

    signal = latest_data.get("Crossover_Signal", 0)

    result_signal = {
        "symbol": symbol,
        "action": None,
        "price": latest_data["close"],
    }

    if signal == 1.0:
        result_signal["action"] = "BUY"

        result_signal["shares"] = latest_data["Target_Shares"]
    elif signal == -1.0:
        result_signal["action"] = "SELL"

    return result_signal


def check_current_signal(ib, symbol, config):
    df = fetch_historical_data(ib, config, symbol=symbol)

    if df is not None and not df.empty:
        df = calculate_indicators(df, config)
        df = generate_base_trend(df)
        df = apply_volume_filter(df)
        df = apply_adx_filter(df, threshold=config.adx_threshold)
        df = apply_trailing_stop_loss(df, config)
        df = apply_52w_high_filter(df)
        df = generate_signals_from_trend(df)
        df = calculate_dynamic_position(df, config)

        return get_latest_live_signal(df, symbol, config)
    return None


def generate_base_trend(df):
    if df is None or df.empty:
        return df
    df["Trend"] = np.where(df["EMA_Fast"] > df["SMA_Slow"], 1, 0)
    return df


def apply_volume_filter(df):
    if "Volume_SMA" not in df.columns:
        return df
    mask_low_volume = df["volume"] <= df["Volume_SMA"]
    mask_low_volume.iloc[-1] = False
    df.loc[mask_low_volume, "Trend"] = 0
    return df


def apply_adx_filter(df, threshold):
    if "ADX" not in df.columns:
        return df
    mask_weak_trend = df["ADX"] < threshold
    df.loc[mask_weak_trend, "Trend"] = 0
    return df


def apply_trailing_stop_loss(df, config):
    if df is None or df.empty or "ATR" not in df.columns:
        return df
    stop_distance = df["ATR"] * config.atr_stop_multiplier
    rolling_high = df["close"].rolling(window=config.ema_fast, min_periods=1).max()
    df["Trailing_Stop"] = rolling_high - stop_distance
    mask_stop_hit = df["close"] < df["Trailing_Stop"]
    df.loc[mask_stop_hit, "Trend"] = 0
    return df

def apply_52w_high_filter(df):
    """
    Prevents NEW buys at 52-week highs, but does NOT force a sell 
    if you already own the stock and it hits a new high.
    """
    if df is None or df.empty or "high" not in df.columns or "Trend" not in df.columns:
        return df

    # Calculate the 52-week (approx 252 trading days) high.
    # We use shift(1) so today's live high doesn't immediately become the high we are checking against.
    rolling_52w_high = df["high"].shift(1).rolling(window=252, min_periods=1).max()


    # This identifies where a brand new buy (Trend 0 -> 1) would have happened at a peak.
    mask_at_high = df["close"] >= rolling_52w_high
    

    # This way, if we are already holding (Trend was 1), hitting a new high keeps Trend at 1.
    is_new_trend = df["Trend"].shift(1) == 0
    
    # Only kill the trend if it's at a high AND it was trying to start a new position
    mask_to_block = mask_at_high & is_new_trend
    
    df.loc[mask_to_block, "Trend"] = 0
    
    return df


def generate_signals_from_trend(df):
    if df is None or df.empty or "Trend" not in df.columns:
        return df
    df["Crossover_Signal"] = df["Trend"].diff()
    return df


def calculate_dynamic_position(df, config):
    if df is None or df.empty or "ATR" not in df.columns:
        return df
    dollar_risk = config.account_capital * config.risk_per_trade_pct
    stop_distance = df["ATR"] * config.atr_stop_multiplier
    risk_shares = np.floor(dollar_risk / stop_distance)
    max_position_value = config.account_capital * config.max_position_pct
    max_capital_shares = np.floor(max_position_value / df["close"])
    df["Target_Shares"] = np.minimum(risk_shares, max_capital_shares)
    df["Target_Weight"] = (df["Target_Shares"] * df["close"]) / config.account_capital
    df["Target_Weight"] = df["Target_Weight"].clip(upper=1.0)
    return df
