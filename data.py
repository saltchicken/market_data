import pandas as pd
import json
import urllib.request
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


def get_all_us_symbols():
    """
    Fetches all available US stock symbols using the official SEC API.
    """
    print("Fetching all US stock symbols from the SEC...")

    url = "https://www.sec.gov/files/company_tickers_exchange.json"

    headers = {"User-Agent": "PaperTradingBot john.eicher89@gmail.com"}
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req) as response:
            raw_data = json.loads(response.read().decode())

        valid_exchanges = {"Nasdaq", "NYSE", "NYSE AMEX", "CBOE", "BATS"}

        invalid_keywords = ["FUND", "TRUST", "ACQUISITION", "SPAC", "ETF", "PORTFOLIO", 
                            "WARRANT", "WARRANTS", "UNIT", "UNITS", "RIGHT", "RIGHTS", "PREFERRED"]

        symbols = []

        # index 1 = Company Name, index 2 = Ticker, index 3 = Exchange
        for row in raw_data.get("data", []):
            company_name = str(row[1]).upper()
            ticker = str(row[2])
            exchange = str(row[3])

            is_valid_equity = not any(kw in company_name for kw in invalid_keywords)
            is_special_class = len(ticker) == 5 and ticker[-1] in ["W", "U", "R", "Q", "Z"]


            if (
                exchange in valid_exchanges
                and is_valid_equity
                and "-" not in ticker
                and "." not in ticker
                and not is_special_class
            ):
                symbols.append(ticker)

        # Remove any duplicates
        unique_symbols = list(set(symbols))

        major_etfs = ["SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "ARKK"]
        unique_symbols.extend([etf for etf in major_etfs if etf not in unique_symbols])

        unique_symbols.sort()

        return format_symbols_for_ibkr(pd.Series(unique_symbols)).tolist()

    except Exception as e:
        print(f"Failed to fetch SEC symbols: {e}. Falling back to S&P 500.")
        return get_sp500_symbols()


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
