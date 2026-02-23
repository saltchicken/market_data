import pandas as pd
from ib_insync import IB
from config import StrategyConfig
from data import fetch_historical_data
from indicators import calculate_indicators
from strategy import (
    generate_base_trend, apply_volume_filter,
    apply_adx_filter, generate_signals_from_trend,
    calculate_dynamic_position
)

def connect_ibkr():
    ib = IB()
    ib.connect('127.0.0.1', 4002, clientId=1)
    return ib


def get_sp500_symbols():
    print("Fetching latest S&P 500 symbols from Wikipedia...")
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    

    tables = pd.read_html(url, storage_options={'User-Agent': 'Mozilla/5.0'})
    df = tables[0]
    

    symbols = df['Symbol'].str.replace('.', '-', regex=False).tolist()
    return symbols

def get_latest_live_signal(df, symbol, config):
    if df is None or df.empty:
        return
        
    latest_data = df.iloc[-1]
    
    date = latest_data['date']
    current_price = latest_data['close']
    signal = latest_data['Crossover_Signal']
    
    print(f"\n{'*'*50}")
    print(f"LIVE TRADE SETUP FOR {symbol} ({date})")
    print(f"{'*'*50}")
    print(f"Current Price: ${current_price:.2f}")
    print(f"EMA Fast: ${latest_data['EMA_Fast']:.2f} | SMA Slow: ${latest_data['SMA_Slow']:.2f}")
    print(f"ADX: {latest_data['ADX']:.2f} | ATR: ${latest_data['ATR']:.2f}")
    
    print("-" * 50)
    if signal == 1.0:
        print("🚨🚀🔥 ACTION: EXECUTING BUY SIGNAL 🚨🚀🔥")
        print(f"Target Allocation: {latest_data['Target_Shares']} Shares ({latest_data['Target_Weight'] * 100:.2f}% of capital)")
        print(f"Stop Loss Reference: ${current_price - (latest_data['ATR'] * config.atr_stop_multiplier):.2f}")
    elif signal == -1.0:
        print("🚨❄️📉 ACTION: EXECUTING SELL SIGNAL 🚨❄️📉")
        print("Reason: Bearish crossover confirmed or filters failed.")
    elif latest_data['Trend'] == 1.0:
        print("🟢 HOLDING LONG: Trend is currently bullish, but no new entry triggered today.")
    else:
        print("⚪ NO ACTION: Market is flat, bearish, or blocked by volume/ADX filters.")
    print(f"{'*'*50}\n")

def check_current_signal(ib, symbol, config):
    print(f"Fetching latest data for {symbol}...")

    df = fetch_historical_data(ib, config, symbol=symbol)
    
    if df is not None and not df.empty:
        df = calculate_indicators(df, config)
        df = generate_base_trend(df) 
        df = apply_volume_filter(df)
        df = apply_adx_filter(df, threshold=config.adx_threshold)
        df = generate_signals_from_trend(df) 
        df = calculate_dynamic_position(df, config)
        
        get_latest_live_signal(df, symbol, config)
    else:
        print(f"No data returned for {symbol}.")

def main():
    ib = connect_ibkr()
    config = StrategyConfig()
    

    symbols_to_test = get_sp500_symbols()
    
    print(f"Found {len(symbols_to_test)} symbols. Beginning scan...")
    
    for i, sym in enumerate(symbols_to_test):
        print(f"Processing {i+1}/{len(symbols_to_test)}...")
        

        # If a symbol is delisted or lacks permissions, it won't crash the script.
        try:
            check_current_signal(ib, sym, config)
        except Exception as e:
            print(f"‼️ Error processing {sym}: {e}")
            

        # If you see pacing errors, increase this to 3-5 seconds.
        ib.sleep(4)

    ib.disconnect()

if __name__ == '__main__':
    main()
