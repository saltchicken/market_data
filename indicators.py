import numpy as np
import pandas as pd


def _calculate_true_range(df):
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()

    # Vectorized max across the three columns
    return pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)


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

    df["up_move"] = df["high"] - df["high"].shift(1)
    df["down_move"] = df["low"].shift(1) - df["low"]
    df["+DM"] = np.where(
        (df["up_move"] > df["down_move"]) & (df["up_move"] > 0), df["up_move"], 0
    )
    df["-DM"] = np.where(
        (df["down_move"] > df["up_move"]) & (df["down_move"] > 0), df["down_move"], 0
    )

    df["TR_smooth"] = df["TR"].ewm(alpha=1 / window, adjust=False).mean()
    df["+DM_smooth"] = df["+DM"].ewm(alpha=1 / window, adjust=False).mean()
    df["-DM_smooth"] = df["-DM"].ewm(alpha=1 / window, adjust=False).mean()

    df["+DI"] = 100 * (df["+DM_smooth"] / df["TR_smooth"])
    df["-DI"] = 100 * (df["-DM_smooth"] / df["TR_smooth"])
    df["DX"] = 100 * (abs(df["+DI"] - df["-DI"]) / (df["+DI"] + df["-DI"]))
    df["ADX"] = df["DX"].ewm(alpha=1 / window, adjust=False).mean()

    cols_to_drop = [
        "TR",
        "up_move",
        "down_move",
        "+DM",
        "-DM",
        "TR_smooth",
        "+DM_smooth",
        "-DM_smooth",
        "+DI",
        "-DI",
        "DX",
    ]
    df.drop(columns=cols_to_drop, inplace=True)
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
