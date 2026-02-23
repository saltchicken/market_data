import numpy as np

# ‼️ Extracted strategy and filtering logic. 
# ‼️ `calculate_pnl` and `calculate_performance_metrics` were completely deleted from this logic pipeline.
def generate_base_trend(df):
    if df is None or df.empty:
        return df
    df['Trend'] = np.where(df['EMA_Fast'] > df['SMA_Slow'], 1, 0)
    return df

def apply_volume_filter(df):
    if 'Volume_SMA' not in df.columns:
        return df
    
    mask_low_volume = df['volume'] <= df['Volume_SMA']
    df.loc[mask_low_volume, 'Trend'] = 0
    return df

def apply_adx_filter(df, threshold):
    if 'ADX' not in df.columns:
        return df
        
    mask_weak_trend = df['ADX'] < threshold
    df.loc[mask_weak_trend, 'Trend'] = 0
    return df

def generate_signals_from_trend(df):
    if df is None or df.empty or 'Trend' not in df.columns:
        return df
        
    df['Crossover_Signal'] = df['Trend'].diff()
    return df

def calculate_dynamic_position(df, config):
    if df is None or df.empty or 'ATR' not in df.columns:
        return df
        
    dollar_risk = config.account_capital * config.risk_per_trade_pct
    stop_distance = df['ATR'] * config.atr_stop_multiplier
    
    df['Target_Shares'] = np.floor(dollar_risk / stop_distance)
    df['Target_Weight'] = (df['Target_Shares'] * df['close']) / config.account_capital
    df['Target_Weight'] = df['Target_Weight'].clip(upper=1.0)
    
    return df
