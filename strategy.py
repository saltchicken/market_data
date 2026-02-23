import numpy as np


def generate_base_trend(df):
    if df is None or df.empty:
        return df
    df["Trend"] = np.where(df["EMA_Fast"] > df["SMA_Slow"], 1, 0)
    return df


def apply_volume_filter(df):
    if "Volume_SMA" not in df.columns:
        return df

    mask_low_volume = df["volume"] <= df["Volume_SMA"]
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

    # Limits the total position size to a percentage of your account capital
    max_position_value = config.account_capital * config.max_position_pct
    max_capital_shares = np.floor(max_position_value / df["close"])

    df["Target_Shares"] = np.minimum(risk_shares, max_capital_shares)

    df["Target_Weight"] = (df["Target_Shares"] * df["close"]) / config.account_capital
    df["Target_Weight"] = df["Target_Weight"].clip(upper=1.0)

    return df
