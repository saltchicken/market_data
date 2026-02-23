from ib_insync import *
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def connect_ibkr():
    ib = IB()
    ib.connect('127.0.0.1', 4002, clientId=1)
    return ib

def fetch_historical_data(ib, symbol='SPY'):
    contract = Stock(symbol, 'SMART', 'USD')
    bars = ib.reqHistoricalData(
        contract,
        endDateTime='',
        durationStr='1 Y',
        barSizeSetting='1 day',
        whatToShow='TRADES',
        useRTH=True,
        formatDate=1
    )
    return util.df(bars)

def add_volume_indicators(df, window=20):
    if df is None or df.empty or 'volume' not in df.columns:
        return df
    df['Volume_SMA'] = df['volume'].rolling(window=window).mean()
    return df

def add_adx_indicator(df, window=14):
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

def calculate_indicators(df):
    if df is None or df.empty:
        return df
    
    df['SMA_50'] = df['close'].rolling(window=50).mean()
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    
    df = add_volume_indicators(df)
    df = add_adx_indicator(df)
    
    return df

# ‼️ Extracted logic to define the base trend state (1 for Bullish posture, 0 for Flat/Bearish)
# ‼️ We no longer calculate the diff() here. We wait until all filters evaluate the state.
def generate_base_trend(df):
    if df is None or df.empty:
        return df
    df['Trend'] = np.where(df['EMA_20'] > df['SMA_50'], 1, 0)
    return df

# ‼️ The filter now modifies the ongoing Trend state, knocking it to 0 if volume is lacking
def apply_volume_filter(df):
    if 'Volume_SMA' not in df.columns:
        return df
    
    mask_low_volume = df['volume'] <= df['Volume_SMA']
    df.loc[mask_low_volume, 'Trend'] = 0
    return df

# ‼️ The filter modifies the Trend state, knocking it to 0 if ADX shows a weak trend
def apply_adx_filter(df, threshold=25):
    if 'ADX' not in df.columns:
        return df
        
    mask_weak_trend = df['ADX'] < threshold
    df.loc[mask_weak_trend, 'Trend'] = 0
    return df

# ‼️ Extracted logic to generate the actual entry/exit events from the final filtered state
def generate_signals_from_trend(df):
    if df is None or df.empty or 'Trend' not in df.columns:
        return df
        
    # ‼️ We now diff() the fully filtered state. 
    # A transition from 0 to 1 means MAs are crossed AND Volume is high AND ADX > 25.
    df['Crossover_Signal'] = df['Trend'].diff()
    return df

def calculate_pnl(df):
    if df is None or df.empty or 'Crossover_Signal' not in df.columns:
        return df
    
    df['Position'] = np.nan
    df.loc[df['Crossover_Signal'] == 1.0, 'Position'] = 1
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
    ax.plot(df['date'], df['SMA_50'], label='SMA 50', color='blue', linestyle='--')
    ax.plot(df['date'], df['EMA_20'], label='EMA 20', color='orange', linestyle='-.')

    buy_signals = df[df['Crossover_Signal'] == 1.0]
    ax.scatter(buy_signals['date'], buy_signals['EMA_20'], marker='^', color='green', label='Buy Signal', s=120, zorder=5)

    sell_signals = df[df['Crossover_Signal'] == -1.0]
    ax.scatter(sell_signals['date'], sell_signals['EMA_20'], marker='v', color='red', label='Sell Signal', s=120, zorder=5)

    ax.set_title(f'{symbol} Price with Filtered EMA/SMA Crossovers')
    ax.set_ylabel('Price (USD)')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)

def plot_volume_chart(ax, df):
    ax.bar(df['date'], df['volume'], color='gray', alpha=0.5, label='Volume')
    if 'Volume_SMA' in df.columns:
        ax.plot(df['date'], df['Volume_SMA'], color='blue', label='Volume SMA (20)', linewidth=1.5)
    
    ax.set_ylabel('Volume')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)

def plot_adx_chart(ax, df):
    if 'ADX' in df.columns:
        ax.plot(df['date'], df['ADX'], color='purple', label='ADX (14)')
        ax.axhline(25, color='red', linestyle='--', alpha=0.7, label='Trend Threshold (25)')
        
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

def plot_signals(df, symbol):
    if df is None or df.empty:
        print(f"No data to plot for {symbol}.")
        return

    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(14, 15), sharex=True, gridspec_kw={'height_ratios': [3, 1, 1, 2]})
    
    plot_price_chart(ax1, df, symbol)
    plot_volume_chart(ax2, df)
    plot_adx_chart(ax3, df)
    plot_pnl_chart(ax4, df)

    plt.tight_layout()
    plt.show()

def run_backtest(ib, symbol):
    print(f"\n{'='*50}")
    print(f"Running Backtest for {symbol}")
    print(f"{'='*50}")

    df = fetch_historical_data(ib, symbol=symbol)
    
    if df is not None and not df.empty:
        df = calculate_indicators(df)
        
        # ‼️ Updated pipeline: Build State -> Constrain State -> Extract Event
        df = generate_base_trend(df) 
        df = apply_volume_filter(df)
        df = apply_adx_filter(df, threshold=25)
        df = generate_signals_from_trend(df) 
        
        df = calculate_pnl(df)
        metrics = calculate_performance_metrics(df)
        
        trade_events = df[df['Crossover_Signal'] != 0].dropna()
        
        print("Filtered Historical Crossover Events (1.0 = Buy, -1.0 = Sell):")
        if not trade_events.empty:
            print(trade_events[['date', 'close', 'volume', 'ADX', 'Crossover_Signal']].tail(10))
        else:
            print("No crossover events triggered for this symbol.")
            
        print(f"\n--- {symbol} Strategy Performance Metrics ---")
        for metric, value in metrics.items():
            print(f"{metric}: {value}")
        print("----------------------------------------\n")
        
        plot_signals(df, symbol)
    else:
        print(f"No data returned for {symbol}.")


def main():
    ib = connect_ibkr()
    
    symbols_to_test = ['CLOV', 'MSFT', 'IWM']
    
    for sym in symbols_to_test:
        run_backtest(ib, sym)

    ib.disconnect()

if __name__ == '__main__':
    main()
