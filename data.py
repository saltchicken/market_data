import pandas as pd
import json
import urllib.request
import os
from ib_insync import Stock, util


def format_symbols_for_ibkr(symbol_series):
    return symbol_series.str.replace(".", " ", regex=False).str.replace(
        "-", " ", regex=False
    )


def get_bad_symbols(filename="bad_symbols.txt"):
    bad_symbols = {"AAS"}
    if os.path.exists(filename):
        with open(filename, "r") as f:
            bad_symbols.update(f.read().splitlines())
    return bad_symbols


def _fetch_sec_raw_data():
    """
    Isolates network I/O from data parsing.
    """
    url = "https://www.sec.gov/files/company_tickers_exchange.json"
    headers = {"User-Agent": "PaperTradingBot john.eicher89@gmail.com"}
    req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())


def _append_major_etfs(symbols_list):
    """
    without cluttering the main parsing loop.
    """
    major_etfs = ["SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "ARKK"]
    existing_set = set(symbols_list)
    symbols_list.extend([etf for etf in major_etfs if etf not in existing_set])
    return symbols_list


def get_all_us_symbols():
    """
    Fetches all available US stock symbols using the official SEC API.
    """
    print("Fetching all US stock symbols from the SEC...")

    try:
        raw_data = _fetch_sec_raw_data()
        bad_symbols = get_bad_symbols()

        # index 1 = Company Name, index 2 = Ticker, index 3 = Exchange
        symbols = [
            str(row[2])
            for row in raw_data.get("data", [])
            if str(row[2]) not in bad_symbols
        ]

        unique_symbols = list(set(symbols))
        unique_symbols = _append_major_etfs(unique_symbols)
        unique_symbols.sort()

        return format_symbols_for_ibkr(pd.Series(unique_symbols)).tolist()

    except Exception as e:
        print(f"Failed to fetch SEC symbols: {e}. Falling back to S&P 500.")
        return get_sp500_symbols()


def get_sp500_symbols():
    print("Fetching latest S&P 500 symbols from Wikipedia...")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    # we need to ensure Wikipedia doesn't crash the script too.
    try:
        tables = pd.read_html(url, storage_options={"User-Agent": "Mozilla/5.0"})
        df = tables[0]

        bad_symbols = get_bad_symbols()
        filtered_symbols = df[~df["Symbol"].isin(bad_symbols)]["Symbol"]

        symbols = format_symbols_for_ibkr(filtered_symbols).tolist()
        return symbols
    except Exception as e:
        print(f"‼️ Failed to fetch S&P 500 symbols from Wikipedia: {e}.")
        return []


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
