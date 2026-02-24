import pandas as pd
from ib_insync import Stock, util


def format_symbols_for_ibkr(symbol_series):
    return symbol_series.str.replace(".", " ", regex=False).str.replace(
        "-", " ", regex=False
    )


def get_sp500_symbols():
    print("Fetching latest S&P 500 symbols from Wikipedia...")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(url, storage_options={"User-Agent": "Mozilla/5.0"})
    df = tables[0]
    symbols = format_symbols_for_ibkr(df["Symbol"]).tolist()
    return symbols


def build_end_date(target_date_str=None):
    if target_date_str is None:
        return ""
    else:
        return f"{target_date_str} 23:59:59"


def fetch_historical_data(ib, config, symbol="SPY", end_date_str=None):
    contract = Stock(symbol, "SMART", "USD")
    target_end = build_end_date(end_date_str)

    bars = ib.reqHistoricalData(
        contract,
        endDateTime=target_end,
        durationStr=config.lookback_duration,
        barSizeSetting="1 day",
        whatToShow="TRADES",
        useRTH=True,
        formatDate=1,
    )
    return util.df(bars)
