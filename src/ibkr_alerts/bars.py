import logging
import datetime
import math
from ib_insync import IB, Stock, Ticker
from .alerts import trigger_alert

logger = logging.getLogger("ibkr_alerts")


class MarketOpenMonitor:
    """
    Subscribes to raw Tick-by-Tick trade data specifically targeting the 
    opening print (for gaps) and aggregating the first 30m candle.
    """

    def __init__(self, ib: IB, targets_dict: dict):
        self.ib = ib
        self.targets_dict = targets_dict
        self.live_tickers = {}

        # State tracking dictionaries
        self.thirty_min_bars = {}
        self.daily_cum_volume = {}
        self.last_processed_price = {}

        # Assumes the system timezone is set to PST/PDT
        self.market_open_time = datetime.time(6, 30)
        self.market_cutoff_time = datetime.time(7, 0)

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
        if t_time < self.market_open_time or t_time >= self.market_cutoff_time:
            return

        # 1. HANDLE THE MARKET OPEN PRINT
        if symbol not in self.thirty_min_bars:
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

            # Initialize the 30m candle state
            self.thirty_min_bars[symbol] = {
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": shares_traded,
                "gap_pct": gap_pct
            }
        
        # 2. BUILD THE REST OF THE 30M CANDLE
        else:
            bar = self.thirty_min_bars[symbol]
            bar["high"] = max(bar["high"], price)
            bar["low"] = min(bar["low"], price)
            bar["close"] = price
            bar["volume"] += shares_traded


    def finalize_candles(self):
        """Called automatically at 07:01 to summarize and alert the completed 30m candles."""
        logger.info("=== FIRST 30m CANDLE SUMMARY ===")
        for symbol, bar in self.thirty_min_bars.items():
            summary = (
                f"[{symbol}] 30m | "
                f"O: ${bar['open']:.2f} H: ${bar['high']:.2f} "
                f"L: ${bar['low']:.2f} C: ${bar['close']:.2f} | "
                f"Vol: {bar['volume']:,} | Gap: {bar['gap_pct']:+.2f}%"
            )
            logger.info(summary)
            trigger_alert("30m CANDLE CLOSED", summary)


def monitor_market_open(ib: IB, targets_dict: dict) -> MarketOpenMonitor:
    """Initializes and returns the live monitor."""
    logger.info("Initializing live tick-by-tick data streams...")
    monitor = MarketOpenMonitor(ib, targets_dict)
    
    # Return the builder instance itself so it survives garbage collection
    return monitor.start()
