from ib_insync import *
import pandas as pd

def fetch_and_calculate_averages():
    # Connect to a running instance of TWS or IB Gateway
    ib = IB()
    # Default port is 7497 for paper trading / 7496 for live
    ib.connect('127.0.0.1', 4002, clientId=1)

    # Define the contract you want to trade/backtest
    contract = Stock('SPY', 'SMART', 'USD')

    # Fetch 1 year of daily historical data
    bars = ib.reqHistoricalData(
        contract,
        endDateTime='',
        durationStr='1 Y',
        barSizeSetting='1 day',
        whatToShow='TRADES',
        useRTH=True,
        formatDate=1
    )

    # Convert the IBKR bars into a Pandas DataFrame for easier calculation
    df = util.df(bars)

    if df is not None and not df.empty:
        # ‼️ Calculate the 50-period Simple Moving Average (SMA) using a rolling window
        df['SMA_50'] = df['close'].rolling(window=50).mean()

        # ‼️ Calculate the 50-period Exponential Moving Average (EMA) using exponential weighting
        df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()

        # Display the most recent 10 days to compare the lag and responsiveness
        print(df[['date', 'close', 'SMA_50', 'EMA_50']].tail(10))
    else:
        print("No data returned.")

    # Always disconnect when finished
    ib.disconnect()

if __name__ == '__main__':
    fetch_and_calculate_averages()
