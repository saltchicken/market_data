import numpy as np
from data import fetch_historical_data
from indicators import calculate_indicators


def get_latest_live_signal(df, symbol, config):
    if df is None or df.empty:
        return None

    latest_data = df.iloc[-1]

    crossover = latest_data.get("Crossover_Signal", 0)
    current_trend = latest_data.get("Trend", 0)

    result_signal = {
        "symbol": symbol,
        "action": None,
        "price": latest_data["close"],
    }

    # This prevents the bot from trapping a position if restarted after the crossover day.
    if crossover == 1.0:
        result_signal["action"] = "BUY"
        result_signal["shares"] = latest_data["Target_Shares"]
    elif current_trend == 0.0:
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


def _was_previous_downtrend(df):
    """
    ‼️ NEW: Extracted helper to determine if the prior bar was technically a downtrend,
    independent of any mutations made to the 'Trend' column by other filters.
    """
    return df["EMA_Fast"].shift(1) <= df["SMA_Slow"].shift(1)


def apply_52w_high_filter(df):
    if df is None or df.empty or "high" not in df.columns or "Trend" not in df.columns:
        return df

    rolling_52w_high = df["high"].shift(1).rolling(window=252, min_periods=1).max()
    mask_at_high = df["close"] >= rolling_52w_high

    is_new_trend = _was_previous_downtrend(df)

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

    # Avoid division by zero if ATR is unexpectedly 0

    safe_stop_distance = np.where(stop_distance == 0, 1e-9, stop_distance)
    risk_shares = np.floor(dollar_risk / safe_stop_distance)

    max_position_value_by_pct = config.account_capital * config.max_position_pct
    actual_max_position_value = min(max_position_value_by_pct, config.max_position_usd)

    max_capital_shares = np.floor(actual_max_position_value / df["close"])

    df["Target_Shares"] = np.minimum(risk_shares, max_capital_shares)

    df["Target_Shares"] = np.maximum(df["Target_Shares"], 1)

    df["Target_Weight"] = (df["Target_Shares"] * df["close"]) / config.account_capital
    df["Target_Weight"] = df["Target_Weight"].clip(upper=1.0)
    return df
