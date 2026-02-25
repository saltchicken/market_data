import numpy as np
import pandas as pd


def _calculate_true_range(df):
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()

    return pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)


def _calculate_directional_movement(df):
    """
    Extracted the raw up/down movement logic for ADX to keep
    the main indicator function clean.
    """
    up_move = df["high"] - df["high"].shift(1)
    down_move = df["low"].shift(1) - df["low"]

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    return plus_dm, minus_dm


def add_atr_indicator(df, window):
    if df is None or df.empty:
        return df

    df["TR"] = _calculate_true_range(df)
    df["ATR"] = df["TR"].ewm(alpha=1 / window, adjust=False).mean()
    df.drop(columns=["TR"], inplace=True)
    return df


def add_volume_indicators(df, window):
    if df is None or df.empty or "volume" not in df.columns:
        return df
    df["Volume_SMA"] = df["volume"].rolling(window=window).mean()
    return df


def add_adx_indicator(df, window):
    if df is None or df.empty:
        return df

    df["TR"] = _calculate_true_range(df)
    plus_dm, minus_dm = _calculate_directional_movement(df)

    df["TR_smooth"] = df["TR"].ewm(alpha=1 / window, adjust=False).mean()

    # Wrap in pd.Series to use .ewm()
    df["+DM_smooth"] = pd.Series(plus_dm).ewm(alpha=1 / window, adjust=False).mean()
    df["-DM_smooth"] = pd.Series(minus_dm).ewm(alpha=1 / window, adjust=False).mean()

    plus_di = 100 * (df["+DM_smooth"] / df["TR_smooth"])
    minus_di = 100 * (df["-DM_smooth"] / df["TR_smooth"])

    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
    df["ADX"] = dx.ewm(alpha=1 / window, adjust=False).mean()

    # Clean up intermediate columns to avoid dataframe bloat
    df.drop(columns=["TR", "TR_smooth", "+DM_smooth", "-DM_smooth"], inplace=True)
    return df


def calculate_indicators(df, config):
    if df is None or df.empty:
        return df

    df["SMA_Slow"] = df["close"].rolling(window=config.sma_slow).mean()
    df["EMA_Fast"] = df["close"].ewm(span=config.ema_fast, adjust=False).mean()

    df = add_volume_indicators(df, config.volume_window)
    df = add_adx_indicator(df, config.adx_window)
    df = add_atr_indicator(df, config.adx_window)

    return df
