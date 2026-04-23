import logging
import datetime
import math
from ib_insync import IB, Stock, Ticker

logger = logging.getLogger(__name__)

class MarketOpenMonitor:
    """Subscribes to live trade data and targets the opening print and standard candles."""

    def __init__(self, ib: IB, targets_dict: dict):
        self.ib = ib
        self.targets_dict = targets_dict
        self.live_tickers = {}

        self.bars = {}
        self.daily_cum_volume = {}
        self.last_processed_price = {}

        self.market_open_time = datetime.time(6, 30)
        self.time_5m = datetime.time(6, 35)
        self.time_15m = datetime.time(6, 45)
        self.time_30m = datetime.time(7, 0)
        
        self.alerted_5m = False
        self.alerted_15m = False
        self.alerted_30m = False

    def start(self) -> 'MarketOpenMonitor':
        symbols = list(self.targets_dict.keys())
        contracts = [Stock(symbol, "SMART", "USD") for symbol in symbols]
        self.ib.qualifyContracts(*contracts)

        for contract in contracts:
            ticker = self.ib.reqMktData(contract, "", False, False)
            ticker.updateEvent += self._on_tick_update
            self.live_tickers[contract.symbol] = ticker

            logger.info(f"Subscribed to live tick stream for {contract.symbol}")
            self.ib.sleep(0.5)

        return self

    def _on_tick_update(self, ticker: Ticker):
        if math.isnan(ticker.last) or ticker.last <= 0.0: return

        symbol = ticker.contract.symbol
        price = ticker.last
        cum_vol = ticker.volume

        if math.isnan(cum_vol):
            size = 0
        else:
            prev_cum_vol = self.daily_cum_volume.get(symbol, cum_vol)
            size = cum_vol - prev_cum_vol
            self.daily_cum_volume[symbol] = cum_vol

        shares_traded = int(size * 100)

        if shares_traded <= 0 and price == self.last_processed_price.get(symbol):
            return

        self.last_processed_price[symbol] = price
        trade_time = (ticker.time.astimezone() if ticker.time else datetime.datetime.now().astimezone())
        t_time = trade_time.time()

        if t_time < self.market_open_time or t_time >= self.time_30m: return

        if symbol not in self.bars:
            prev_close = self.targets_dict.get(symbol, {}).get("prev_close")
            gap_pct = 0.0
            gap_str = "N/A"
            
            if prev_close and prev_close > 0:
                gap_pct = ((price - prev_close) / prev_close) * 100
                gap_str = f"{gap_pct:+.2f}%"

            logger.info(f"🔔 OPEN [{symbol}]: ${price:.2f} | Gap: {gap_str} | Prev Close: ${prev_close}")

            self.bars[symbol] = {
                "open": price,
                "gap_pct": gap_pct,
                "5m": {"high": price, "low": price, "close": price, "volume": shares_traded},
                "15m": {"high": price, "low": price, "close": price, "volume": shares_traded},
                "30m": {"high": price, "low": price, "close": price, "volume": shares_traded}
            }
        
        else:
            b = self.bars[symbol]
            if t_time < self.time_5m:
                b["5m"]["high"] = max(b["5m"]["high"], price)
                b["5m"]["low"] = min(b["5m"]["low"], price)
                b["5m"]["close"] = price
                b["5m"]["volume"] += shares_traded
                
            if t_time < self.time_15m:
                b["15m"]["high"] = max(b["15m"]["high"], price)
                b["15m"]["low"] = min(b["15m"]["low"], price)
                b["15m"]["close"] = price
                b["15m"]["volume"] += shares_traded
                
            if t_time < self.time_30m:
                b["30m"]["high"] = max(b["30m"]["high"], price)
                b["30m"]["low"] = min(b["30m"]["low"], price)
                b["30m"]["close"] = price
                b["30m"]["volume"] += shares_traded

    def check_time_alerts(self, current_time: datetime.time):
        if current_time >= self.time_5m and not self.alerted_5m:
            self._alert_timeframe("5m")
            self.alerted_5m = True
            
        if current_time >= self.time_15m and not self.alerted_15m:
            self._alert_timeframe("15m")
            self.alerted_15m = True
            
        if current_time >= self.time_30m and not self.alerted_30m:
            self._alert_timeframe("30m")
            self.alerted_30m = True

    def _alert_timeframe(self, tf: str):
        if not self.bars: return
            
        logger.info(f"=== FIRST {tf} CANDLE SUMMARY ===")
        for symbol, data in self.bars.items():
            bar = data[tf]
            logger.info(
                f"[{symbol}] {tf} | O: ${data['open']:.2f} H: ${bar['high']:.2f} "
                f"L: ${bar['low']:.2f} C: ${bar['close']:.2f} | Vol: {bar['volume']:,}"
            )
            
            # --- NEW FEATURE: 30m ATR Alert Check ---
            if tf == "30m":
                atr_14 = self.targets_dict.get(symbol, {}).get("atr_14")
                if atr_14 and atr_14 > 0:
                    candle_range = bar['high'] - bar['low']
                    target_threshold = atr_14 * 0.25
                    
                    if candle_range > target_threshold:
                        logger.warning(
                            f"🚨 VOLATILITY ALERT: [{symbol}] 30m candle range (${candle_range:.2f}) "
                            f"exceeded 25% of Daily ATR (${target_threshold:.2f})!"
                        )


def monitor_market_open(ib: IB, targets_dict: dict) -> MarketOpenMonitor:
    logger.info("Initializing live tick-by-tick data streams...")
    return MarketOpenMonitor(ib, targets_dict).start()
