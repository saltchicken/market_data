import logging
import datetime
import math
from ib_insync import IB, Stock, Ticker
from .alerts import trigger_alert

logger = logging.getLogger("ibkr_alerts")


class MarketOpenMonitor:
    """
    Subscribes to live trade (250ms snapshots) data specifically targeting the 
    opening print (for gaps) and aggregating the first 5m, 15m, and 30m candles.
    Note that volume is not perfectly accurate due to dropping opening print volume and odd-lot truncation.
    """

    def __init__(self, ib: IB, targets_dict: dict):
        self.ib = ib
        self.targets_dict = targets_dict
        self.live_tickers = {}

        # State tracking dictionaries
        self.bars = {}
        self.daily_cum_volume = {}
        self.last_processed_price = {}

        # Assumes the system timezone is set to PST/PDT
        self.market_open_time = datetime.time(6, 30)
        self.time_5m = datetime.time(6, 35)
        self.time_15m = datetime.time(6, 45)
        self.time_30m = datetime.time(7, 0)
        
        # Alert flags
        self.alerted_5m = False
        self.alerted_15m = False
        self.alerted_30m = False

    def start(self) -> 'MarketOpenMonitor':
        """Qualifies contracts and starts the live trade stream."""
        symbols = list(self.targets_dict.keys())
        contracts = [Stock(symbol, "SMART", "USD") for symbol in symbols]
        self.ib.qualifyContracts(*contracts)

        for contract in contracts:
            # reqMktData provides standard Level 1 streaming
            ticker = self.ib.reqMktData(contract, "", False, False)
            ticker.updateEvent += self._on_tick_update
            self.live_tickers[contract.symbol] = ticker

            logger.info(f"Subscribed to live tick stream for {contract.symbol}")
            # Tiny stagger to prevent overwhelming the socket initially
            self.ib.sleep(0.5)

        return self

    def _on_tick_update(self, ticker: Ticker):
        """Triggered rapidly with Level 1 price/volume snapshots."""
        if math.isnan(ticker.last) or ticker.last <= 0.0:
            return

        symbol = ticker.contract.symbol
        price = ticker.last
        cum_vol = ticker.volume

        # FIX: Avoid poisoning the baseline if IBKR sends NaN volume on the initial ticks
        if math.isnan(cum_vol):
            size = 0
        else:
            # Calculate the delta in cumulative volume
            prev_cum_vol = self.daily_cum_volume.get(symbol, cum_vol)
            size = cum_vol - prev_cum_vol
            self.daily_cum_volume[symbol] = cum_vol

        # IBKR reports cumulative volume for US stocks in lots of 100.
        shares_traded = int(size * 100)

        # Skip processing if neither price nor volume has changed
        if shares_traded <= 0 and price == self.last_processed_price.get(symbol):
            return

        self.last_processed_price[symbol] = price

        # Convert IBKR time to local system timezone (fallback to now if IBKR timestamp delayed)
        trade_time = (
            ticker.time.astimezone()
            if ticker.time
            else datetime.datetime.now().astimezone()
        )
        t_time = trade_time.time()

        # We strictly ONLY want to record data between 06:30:00 and 06:59:59 PST
        if t_time < self.market_open_time or t_time >= self.time_30m:
            return

        # 1. HANDLE THE MARKET OPEN PRINT
        if symbol not in self.bars:
            prev_close = self.targets_dict.get(symbol, {}).get("prev_close")
            gap_pct = 0.0
            gap_str = "N/A"
            
            if prev_close and prev_close > 0:
                gap_pct = ((price - prev_close) / prev_close) * 100
                gap_str = f"{gap_pct:+.2f}%"

            logger.info(f"🔔 OPEN [{symbol}]: ${price:.2f} | Gap: {gap_str} | Prev Close: ${prev_close}")
            trigger_alert(
                "MARKET OPEN GAP", 
                f"{symbol} opened at ${price:.2f} (Gap: {gap_str})"
            )

            # Initialize the candles state for all 3 timeframes
            self.bars[symbol] = {
                "open": price,
                "gap_pct": gap_pct,
                "5m": {"high": price, "low": price, "close": price, "volume": shares_traded},
                "15m": {"high": price, "low": price, "close": price, "volume": shares_traded},
                "30m": {"high": price, "low": price, "close": price, "volume": shares_traded}
            }
        
        # 2. BUILD THE REST OF THE CANDLES
        else:
            b = self.bars[symbol]
            
            # Keep updating 5m data if before 06:35
            if t_time < self.time_5m:
                b["5m"]["high"] = max(b["5m"]["high"], price)
                b["5m"]["low"] = min(b["5m"]["low"], price)
                b["5m"]["close"] = price
                b["5m"]["volume"] += shares_traded
                
            # Keep updating 15m data if before 06:45
            if t_time < self.time_15m:
                b["15m"]["high"] = max(b["15m"]["high"], price)
                b["15m"]["low"] = min(b["15m"]["low"], price)
                b["15m"]["close"] = price
                b["15m"]["volume"] += shares_traded
                
            # Keep updating 30m data if before 07:00
            if t_time < self.time_30m:
                b["30m"]["high"] = max(b["30m"]["high"], price)
                b["30m"]["low"] = min(b["30m"]["low"], price)
                b["30m"]["close"] = price
                b["30m"]["volume"] += shares_traded

    def check_time_alerts(self, current_time: datetime.time):
        """Checks the current time and fires alerts for completed candles."""
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
        """Summarizes and alerts the data for a specific timeframe."""
        if not self.bars:
            return
            
        logger.info(f"=== FIRST {tf} CANDLE SUMMARY ===")
        for symbol, data in self.bars.items():
            bar = data[tf]
            summary = (
                f"[{symbol}] {tf} | "
                f"O: ${data['open']:.2f} H: ${bar['high']:.2f} "
                f"L: ${bar['low']:.2f} C: ${bar['close']:.2f} | "
                f"Vol: {bar['volume']:,}"
            )
            logger.info(summary)
            trigger_alert(f"{tf} CANDLE CLOSED", summary)

def monitor_market_open(ib: IB, targets_dict: dict) -> MarketOpenMonitor:
    """Initializes and returns the live monitor."""
    logger.info("Initializing live tick-by-tick data streams...")
    monitor = MarketOpenMonitor(ib, targets_dict)
    
    # Return the builder instance itself so it survives garbage collection
    return monitor.start()
