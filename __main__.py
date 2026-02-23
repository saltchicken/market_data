from ib_insync import IB
from config import StrategyConfig
from data import fetch_historical_data
from indicators import calculate_indicators
from strategy import (
    generate_base_trend, apply_volume_filter,
    apply_adx_filter, generate_signals_from_trend,
    calculate_dynamic_position
)

# ‼️ Removed all matplotlib imports, price plotting, volume plotting, and PnL plotting functions.

def connect_ibkr():
    ib = IB()
    ib.connect('127.0.0.1', 4002, clientId=1)
    return ib

def get_latest_live_signal(df, symbol, config):
    if df is None or df.empty:
        return
        
    latest_data = df.iloc[-1]
    
    date = latest_data['date']
    current_price = latest_data['close']
    signal = latest_data['Crossover_Signal']
    
    # ‼️ Streamlined the console output to act as a pure real-time dashboard
    print(f"\n{'*'*50}")
    print(f"LIVE TRADE SETUP FOR {symbol} ({date})")
    print(f"{'*'*50}")
    print(f"Current Price: ${current_price:.2f}")
    print(f"EMA Fast: ${latest_data['EMA_Fast']:.2f} | SMA Slow: ${latest_data['SMA_Slow']:.2f}")
    print(f"ADX: {latest_data['ADX']:.2f} | ATR: ${latest_data['ATR']:.2f}")
    
    print("-" * 50)
    if signal == 1.0:
        print("🚨 ACTION: EXECUTING BUY SIGNAL 🚨")
        print(f"Target Allocation: {latest_data['Target_Shares']} Shares ({latest_data['Target_Weight'] * 100:.2f}% of capital)")
        print(f"Stop Loss Reference: ${current_price - (latest_data['ATR'] * config.atr_stop_multiplier):.2f}")
    elif signal == -1.0:
        print("🚨 ACTION: EXECUTING SELL SIGNAL 🚨")
        print("Reason: Bearish crossover confirmed or filters failed.")
    elif latest_data['Trend'] == 1.0:
        print("🟢 HOLDING LONG: Trend is currently bullish, but no new entry triggered today.")
    else:
        print("⚪ NO ACTION: Market is flat, bearish, or blocked by volume/ADX filters.")
    print(f"{'*'*50}\n")

# ‼️ Renamed from `run_backtest` to `check_current_signal`
def check_current_signal(ib, symbol, config):
    print(f"Fetching latest data for {symbol}...")

    df = fetch_historical_data(ib, config, symbol=symbol)
    
    if df is not None and not df.empty:
        # ‼️ Linear processing pipeline ending exactly at signal generation
        df = calculate_indicators(df, config)
        df = generate_base_trend(df) 
        df = apply_volume_filter(df)
        df = apply_adx_filter(df, threshold=config.adx_threshold)
        df = generate_signals_from_trend(df) 
        df = calculate_dynamic_position(df, config)
        
        # ‼️ Immediately read the last row instead of calculating entire historic PnL arrays
        get_latest_live_signal(df, symbol, config)
    else:
        print(f"No data returned for {symbol}.")


def main():
    ib = connect_ibkr()
    config = StrategyConfig()
    
    symbols_to_test = ['SPY', 'QQQ', 'IWM']
    
    for sym in symbols_to_test:
        check_current_signal(ib, sym, config)

    ib.disconnect()

if __name__ == '__main__':
    main()
