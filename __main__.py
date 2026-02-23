from ib_insync import *
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ‼️ Extracted configuration class to centralize all tweakable strategy parameters
class StrategyConfig:
    def __init__(self):
        # Account & Risk Settings
        self.account_capital = 100000
        self.risk_per_trade_pct = 0.01  # 1% risk per trade
        self.atr_stop_multiplier = 2.0
        
        # Indicator Settings
        self.sma_slow = 50
        self.ema_fast = 20
        self.volume_window = 20
        self.adx_window = 14
        self.adx_threshold = 25
        
        # Backtest Settings
        self.warmup_days = 252
        self.lookback_duration = '2 Y'

def connect_ibkr():
    ib = IB()
    ib.connect('127.0.0.1', 4002, clientId=1)
    return ib

def build_end_date(target_date_str=None):
    if target_date_str is None:
        return '' 
    else:
        return f"{target_date_str} 23:59:59"

# ‼️ Updated to utilize the config for the lookback duration
def fetch_historical_data(ib, config, symbol='SPY', end_date_str=None):
    contract = Stock(symbol, 'SMART', 'USD')
    target_end = build_end_date(end_date_str)
    
    bars = ib.reqHistoricalData(
        contract,
        endDateTime=target_end,
        durationStr=config.lookback_duration, 
        barSizeSetting='1 day',
        whatToShow='TRADES',
        useRTH=True,
        formatDate=1
    )
    return util.df(bars)

def add_atr_indicator(df, window):
    if df is None or df.empty:
        return df
    
    df['prev_close'] = df['close'].shift(1)
    df['TR'] = df[['high', 'low', 'prev_close']].apply(
        lambda x: max(x['high'] - x['low'], abs(x['high'] - x['prev_close']), abs(x['low'] - x['prev_close'])), 
        axis=1
    )
    
    df['ATR'] = df['TR'].ewm(alpha=1/window, adjust=False).mean()
    df.drop(columns=['prev_close', 'TR'], inplace=True)
    return df

def add_volume_indicators(df, window):
    if df is None or df.empty or 'volume' not in df.columns:
        return df
    df['Volume_SMA'] = df['volume'].rolling(window=window).mean()
    return df

def add_adx_indicator(df, window):
    if df is None or df.empty:
        return df
    
    df['prev_close'] = df['close'].shift(1)
    df['TR'] = df[['high', 'low', 'prev_close']].apply(
        lambda x: max(x['high'] - x['low'], abs(x['high'] - x['prev_close']), abs(x['low'] - x['prev_close'])), 
        axis=1
    )
    
    df['up_move'] = df['high'] - df['high'].shift(1)
    df['down_move'] = df['low'].shift(1) - df['low']
    df['+DM'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
    df['-DM'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
    
    df['TR_smooth'] = df['TR'].ewm(alpha=1/window, adjust=False).mean()
    df['+DM_smooth'] = df['+DM'].ewm(alpha=1/window, adjust=False).mean()
    df['-DM_smooth'] = df['-DM'].ewm(alpha=1/window, adjust=False).mean()
    
    df['+DI'] = 100 * (df['+DM_smooth'] / df['TR_smooth'])
    df['-DI'] = 100 * (df['-DM_smooth'] / df['TR_smooth'])
    df['DX'] = 100 * (abs(df['+DI'] - df['-DI']) / (df['+DI'] + df['-DI']))
    df['ADX'] = df['DX'].ewm(alpha=1/window, adjust=False).mean()
    
    cols_to_drop = ['prev_close', 'TR', 'up_move', 'down_move', '+DM', '-DM', 'TR_smooth', '+DM_smooth', '-DM_smooth', '+DI', '-DI', 'DX']
    df.drop(columns=cols_to_drop, inplace=True)
    
    return df

# ‼️ Updated to inject indicator lengths dynamically from the config object
def calculate_indicators(df, config):
    if df is None or df.empty:
        return df
    
    df['SMA_Slow'] = df['close'].rolling(window=config.sma_slow).mean()
    df['EMA_Fast'] = df['close'].ewm(span=config.ema_fast, adjust=False).mean()
    
    df = add_volume_indicators(df, config.volume_window)
    df = add_adx_indicator(df, config.adx_window)
    df = add_atr_indicator(df, config.adx_window) # Reusing adx_window for ATR for consistency
    
    return df

def slice_warmup_buffer(df, trading_days):
    if df is None or df.empty:
        return df
    return df.tail(trading_days).reset_index(drop=True)

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

# ‼️ Updated to utilize the config block for risk rules
def calculate_dynamic_position(df, config):
    if df is None or df.empty or 'ATR' not in df.columns:
        return df
        
    dollar_risk = config.account_capital * config.risk_per_trade_pct
    stop_distance = df['ATR'] * config.atr_stop_multiplier
    
    df['Target_Shares'] = np.floor(dollar_risk / stop_distance)
    df['Target_Weight'] = (df['Target_Shares'] * df['close']) / config.account_capital
    df['Target_Weight'] = df['Target_Weight'].clip(upper=1.0)
    
    return df

def calculate_pnl(df):
    if df is None or df.empty or 'Crossover_Signal' not in df.columns:
        return df
    
    df['Position'] = np.nan
    
    buy_mask = df['Crossover_Signal'] == 1.0
    df.loc[buy_mask, 'Position'] = df.loc[buy_mask, 'Target_Weight']
    df.loc[df['Crossover_Signal'] == -1.0, 'Position'] = 0
    
    df['Position'] = df['Position'].ffill().fillna(0)
    df['Daily_Return'] = df['close'].pct_change()
    df['Strategy_Return'] = df['Position'].shift(1) * df['Daily_Return']
    df['Cumulative_Strategy'] = (1 + df['Strategy_Return']).cumprod()
    df['Cumulative_Buy_Hold'] = (1 + df['Daily_Return']).cumprod()
    
    return df

def calculate_performance_metrics(df, risk_free_rate=0.0):
    if df is None or df.empty or 'Strategy_Return' not in df.columns:
        return {}
    
    returns = df['Strategy_Return'].dropna()
    if returns.empty:
        return {}

    total_return = df['Cumulative_Strategy'].iloc[-1] - 1
    days = (df['date'].iloc[-1] - df['date'].iloc[0]).days
    annualized_return = (1 + total_return) ** (365.0 / days) - 1 if days > 0 else 0
    
    daily_volatility = returns.std()
    annualized_volatility = daily_volatility * np.sqrt(252)
    
    if annualized_volatility > 0:
        sharpe_ratio = (annualized_return - risk_free_rate) / annualized_volatility
    else:
        sharpe_ratio = 0.0
        
    rolling_max = df['Cumulative_Strategy'].cummax()
    drawdown = df['Cumulative_Strategy'] / rolling_max - 1
    max_drawdown = drawdown.min()
    
    return {
        'Total Return': f"{total_return:.2%}",
        'Annualized Return': f"{annualized_return:.2%}",
        'Annualized Volatility': f"{annualized_volatility:.2%}",
        'Sharpe Ratio': f"{sharpe_ratio:.2f}",
        'Max Drawdown': f"{max_drawdown:.2%}"
    }

def plot_price_chart(ax, df, symbol):
    ax.plot(df['date'], df['close'], label='Close Price', color='black', alpha=0.5)
    ax.plot(df['date'], df['SMA_Slow'], label='SMA Slow', color='blue', linestyle='--')
    ax.plot(df['date'], df['EMA_Fast'], label='EMA Fast', color='orange', linestyle='-.')

    buy_signals = df[df['Crossover_Signal'] == 1.0]
    ax.scatter(buy_signals['date'], buy_signals['EMA_Fast'], marker='^', color='green', label='Buy Signal', s=120, zorder=5)

    sell_signals = df[df['Crossover_Signal'] == -1.0]
    ax.scatter(sell_signals['date'], sell_signals['EMA_Fast'], marker='v', color='red', label='Sell Signal', s=120, zorder=5)

    ax.set_title(f'{symbol} Price with Filtered EMA/SMA Crossovers')
    ax.set_ylabel('Price (USD)')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)

def plot_volume_chart(ax, df):
    ax.bar(df['date'], df['volume'], color='gray', alpha=0.5, label='Volume')
    if 'Volume_SMA' in df.columns:
        ax.plot(df['date'], df['Volume_SMA'], color='blue', label='Volume SMA', linewidth=1.5)
    
    ax.set_ylabel('Volume')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)

def plot_adx_chart(ax, df, threshold):
    if 'ADX' in df.columns:
        ax.plot(df['date'], df['ADX'], color='purple', label='ADX')
        ax.axhline(threshold, color='red', linestyle='--', alpha=0.7, label=f'Trend Threshold ({threshold})')
        
    ax.set_ylabel('ADX')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)

def plot_pnl_chart(ax, df):
    if 'Cumulative_Strategy' in df.columns and 'Cumulative_Buy_Hold' in df.columns:
        ax.plot(df['date'], df['Cumulative_Buy_Hold'], label='Buy & Hold PnL', color='gray', linestyle='--')
        ax.plot(df['date'], df['Cumulative_Strategy'], label='Strategy PnL', color='green', linewidth=2)
        
    ax.set_ylabel('Cumulative PnL (1.0 = Base)')
    ax.set_xlabel('Date')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis='x', rotation=45)

def plot_signals(df, symbol, config):
    if df is None or df.empty:
        print(f"No data to plot for {symbol}.")
        return

    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(14, 15), sharex=True, gridspec_kw={'height_ratios': [3, 1, 1, 2]})
    
    plot_price_chart(ax1, df, symbol)
    plot_volume_chart(ax2, df)
    plot_adx_chart(ax3, df, config.adx_threshold)
    plot_pnl_chart(ax4, df)

    plt.tight_layout()
    plt.show()

# ‼️ Updated to pass the config object for multiplier references
def get_latest_live_signal(df, symbol, config):
    if df is None or df.empty:
        return
        
    latest_data = df.iloc[-1]
    
    date = latest_data['date']
    current_price = latest_data['close']
    signal = latest_data['Crossover_Signal']
    
    print(f"\n{'*'*40}")
    print(f"LIVE TRADE SETUP FOR {symbol} ({date})")
    print(f"{'*'*40}")
    print(f"Current Price: ${current_price:.2f}")
    print(f"EMA Fast: ${latest_data['EMA_Fast']:.2f} | SMA Slow: ${latest_data['SMA_Slow']:.2f}")
    print(f"ADX: {latest_data['ADX']:.2f} | ATR: ${latest_data['ATR']:.2f}")
    
    print("-" * 40)
    if signal == 1.0:
        print("🚨 ACTION: EXECUTING BUY SIGNAL 🚨")
        print(f"Target Allocation: {latest_data['Target_Shares']} Shares ({latest_data['Target_Weight'] * 100:.2f}% of capital)")
        print(f"Stop Loss Reference: ${current_price - (latest_data['ATR'] * config.atr_stop_multiplier):.2f}")
    elif signal == -1.0:
        print("🚨 ACTION: EXECUTING SELL SIGNAL 🚨")
        print("Reason: Bearish crossover confirmed.")
    elif latest_data['Trend'] == 1.0:
        print("HOLDING LONG: Trend is currently bullish, but no new entry triggered today.")
    else:
        print("NO ACTION: Market is flat, bearish, or blocked by volume/ADX filters.")
    print(f"{'*'*40}\n")

# ‼️ Updated orchestrator to pass the config object through the entire pipeline
def run_backtest(ib, symbol, config):
    print(f"\n{'='*50}")
    print(f"Running Backtest for {symbol}")
    print(f"{'='*50}")

    df = fetch_historical_data(ib, config, symbol=symbol)
    
    if df is not None and not df.empty:
        df = calculate_indicators(df, config)
        df = slice_warmup_buffer(df, trading_days=config.warmup_days)
        
        df = generate_base_trend(df) 
        df = apply_volume_filter(df)
        df = apply_adx_filter(df, threshold=config.adx_threshold)
        df = generate_signals_from_trend(df) 
        
        df = calculate_dynamic_position(df, config)
        
        df = calculate_pnl(df)
        metrics = calculate_performance_metrics(df)
        
        trade_events = df[df['Crossover_Signal'] != 0].dropna()
        
        print("Filtered Historical Crossover Events (1.0 = Buy, -1.0 = Sell):")
        if not trade_events.empty:
            print(trade_events[['date', 'close', 'ATR', 'Target_Weight', 'Crossover_Signal']].tail(10))
        else:
            print("No crossover events triggered for this symbol.")
            
        print(f"\n--- {symbol} Strategy Performance Metrics ---")
        for metric, value in metrics.items():
            print(f"{metric}: {value}")
        print("----------------------------------------\n")
        
        get_latest_live_signal(df, symbol, config)
        plot_signals(df, symbol, config)
    else:
        print(f"No data returned for {symbol}.")


def main():
    ib = connect_ibkr()
    
    # ‼️ Initialize the configuration exactly once and pass it down
    config = StrategyConfig()
    
    symbols_to_test = ['SPY', 'QQQ', 'IWM']
    
    for sym in symbols_to_test:
        run_backtest(ib, sym, config)

    ib.disconnect()

if __name__ == '__main__':
    main()
