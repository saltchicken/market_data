from ib_insync import Stock, util


def build_end_date(target_date_str=None):
    if target_date_str is None:
        return '' 
    else:
        return f"{target_date_str} 23:59:59"

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