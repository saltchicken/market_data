from ib_insync import *
import pandas as pd
import numpy as np

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

def calculate_indicators(df):
    if df is None or df.empty:
        return df
    
    df['SMA_50'] = df['close'].rolling(window=50).mean()
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    
    return df

def generate_signals(df):
    if df is None or df.empty:
        return df
        
    df['Trend'] = np.where(df['EMA_20'] > df['SMA_50'], 1, 0)
    
    # A diff of +1 means the trend went from 0 to 1 (Buy Signal).
    # A diff of -1 means the trend went from 1 to 0 (Sell Signal).
    df['Crossover_Signal'] = df['Trend'].diff()
    
    return df

def main():
    ib = connect_ibkr()
    df = fetch_historical_data(ib)
    
    if df is not None and not df.empty:
        df = calculate_indicators(df)
        df = generate_signals(df) 
        
        # Filter the DataFrame to display only the days where an actual crossover event fired
        trade_events = df[df['Crossover_Signal'] != 0].dropna()
        
        print("Historical Crossover Events (1.0 = Buy, -1.0 = Sell):")
        print(trade_events[['date', 'close', 'EMA_20', 'SMA_50', 'Crossover_Signal']].tail(10))
    else:
        print("No data returned.")

    ib.disconnect()

if __name__ == '__main__':
    main()
