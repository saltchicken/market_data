import logging
import datetime
from ib_insync import IB, Stock, Ticker
from .alerts import trigger_alert

logger = logging.getLogger("ibkr_alerts")


class LiveTradeBarBuilder:
    """
    Subscribes to raw Tick-by-Tick trade data and manually builds OHLCV bars.
    Includes all business logic for gaps, price targets, and volume alerts.
    """

    def __init__(self, ib: IB, targets_dict: dict):
        self.ib = ib
        self.targets_dict = targets_dict
        self.live_tickers = {}

        # State tracking dictionaries
        self.active_5m_bars = {}
        self.active_30m_vols = {}

        # Alert debouncers
        self.alerted_gaps = set()
        self.open_gap_logged = set()
        self.alerted_volume = set()
        self.alerted_buy = set()
        self.alerted_sell = set()

        # Assumes the system timezone is set to PST/PDT
        self.market_open_time = datetime.time(6, 30)

    def _get_5m_boundary(self, dt: datetime.datetime) -> datetime.datetime:
        """Floors a datetime to the nearest 5-minute boundary."""
        minute = (dt.minute // 5) * 5
        return dt.replace(minute=minute, second=0, microsecond=0)

    def _get_30m_boundary(self, dt: datetime.datetime) -> datetime.datetime:
        """Floors a datetime to the nearest 30-minute boundary."""
        minute = (dt.minute // 30) * 30
        return dt.replace(minute=minute, second=0, microsecond=0)

    def start(self) -> dict:
        """Qualifies contracts and starts the live trade stream."""
        symbols = list(self.targets_dict.keys())
        contracts = [Stock(symbol, "SMART", "USD") for symbol in symbols]
        self.ib.qualifyContracts(*contracts)

        for contract in contracts:
            # reqTickByTickData with 'Last' gets every individual trade on the exchange
            ticker = self.ib.reqTickByTickData(contract, "Last")
            ticker.updateEvent += self._on_tick_update
            self.live_tickers[contract.symbol] = ticker

            logger.info(f"Subscribed to live tick stream for {contract.symbol}")
            self.ib.sleep(
                0.1
            )  # Tiny stagger to prevent overwhelming the socket initially

        return self.live_tickers

    def _on_tick_update(self, ticker: Ticker):
        """Triggered whenever a new individual trade (or batch of trades) arrives."""
        if not ticker.tickByTicks:
            return

        symbol = ticker.contract.symbol

        for tick in ticker.tickByTicks:
            # Convert IBKR's UTC tick time to system local time (PST/PDT)
            local_trade_time = tick.time.astimezone()
            self._process_trade(symbol, tick.price, tick.size, local_trade_time)

        # Clear the processed ticks so we don't double-count them
        ticker.tickByTicks.clear()

    def _process_trade(
        self, symbol: str, price: float, size: int, trade_time: datetime.datetime
    ):
        """Routes the raw trade into the appropriate time buckets and runs real-time alerts."""
        trade_5m_boundary = self._get_5m_boundary(trade_time)
        trade_30m_boundary = self._get_30m_boundary(trade_time)

        # --- 1. HANDLE 30-MINUTE VOLUME BUCKET ---
        if symbol not in self.active_30m_vols:
            self.active_30m_vols[symbol] = {
                "boundary": trade_30m_boundary,
                "volume": size,
                "close": price,
            }
        else:
            current_30m = self.active_30m_vols[symbol]
            if trade_30m_boundary > current_30m["boundary"]:
                # The bucket time has rolled over. Log and close it out.
                logger.info(
                    f"📦 [{symbol}] 30m BUCKET COMPLETE | "
                    f"End Close: ${current_30m['close']:.2f} | Total 30m Vol: {current_30m['volume']:,.0f}"
                )
                # Reset bucket
                self.active_30m_vols[symbol] = {
                    "boundary": trade_30m_boundary,
                    "volume": size,
                    "close": price,
                }
            else:
                # Accumulate volume and update latest price
                current_30m["volume"] += size
                current_30m["close"] = price

        # REAL-TIME ALERT: Check Volume Surge (Evaluated every tick)
        t_vol = self.targets_dict.get(symbol, {}).get("target_volume")
        current_30m_vol = self.active_30m_vols[symbol]["volume"]

        if t_vol and current_30m_vol >= t_vol and symbol not in self.alerted_volume:
            trigger_alert(
                "🚨 VOLUME SURGE",
                f"{symbol} 30m running volume ({current_30m_vol:,.0f}) exceeded target ({t_vol:,.0f}) "
                f"early at {trade_time.strftime('%H:%M:%S')}!",
            )
            self.alerted_volume.add(symbol)

        # --- 2. HANDLE 5-MINUTE OHLCV BAR ---
        if symbol not in self.active_5m_bars:
            self.active_5m_bars[symbol] = {
                "boundary": trade_5m_boundary,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": size,
            }
        else:
            current_5m = self.active_5m_bars[symbol]
            if trade_5m_boundary > current_5m["boundary"]:
                # The 5-minute window has rolled over. Evaluate the fully closed bar.
                self._evaluate_closed_5m_bar(symbol, current_5m)

                # Start a fresh 5m bar
                self.active_5m_bars[symbol] = {
                    "boundary": trade_5m_boundary,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": size,
                }
            else:
                # Update the active 5m bar extremes
                current_5m["high"] = max(current_5m["high"], price)
                current_5m["low"] = min(current_5m["low"], price)
                current_5m["close"] = price
                current_5m["volume"] += size

        # --- 3. REAL-TIME TARGET ALERTS (Evaluated every tick to prevent slippage) ---
        t_buy = self.targets_dict.get(symbol, {}).get("target_buy")
        t_sell = self.targets_dict.get(symbol, {}).get("target_sell")

        if t_buy and price <= t_buy and symbol not in self.alerted_buy:
            trigger_alert(
                "💸 BUY TARGET REACHED",
                f"{symbol} dropped to ${price:.2f} (Target: ${t_buy:.2f})!",
            )
            self.alerted_buy.add(symbol)

        if t_sell and price >= t_sell and symbol not in self.alerted_sell:
            trigger_alert(
                "💰 SELL TARGET REACHED",
                f"{symbol} climbed to ${price:.2f} (Target: ${t_sell:.2f})!",
            )
            self.alerted_sell.add(symbol)

    def _evaluate_closed_5m_bar(self, symbol: str, bar: dict):
        """Runs gap checks and logging exclusively on fully closed 5-minute candles."""
        latest_time = bar["boundary"].time()
        latest_close = bar["close"]
        latest_5m_vol = bar["volume"]

        symbol_targets = self.targets_dict.get(symbol, {})
        prev_close = symbol_targets.get("prev_close")

        # --- PREMARKET GAP & MARKET OPEN CALCULATION ---
        gap_str = ""
        if prev_close and prev_close > 0:
            current_change_pct = ((latest_close - prev_close) / prev_close) * 100

            if latest_time < self.market_open_time:
                # 1. PREMARKET: Log as Pre-Gap and check for extreme alerts
                gap_str = f" | Pre-Gap: {current_change_pct:+.2f}%"

                if abs(current_change_pct) >= 5.0 and symbol not in self.alerted_gaps:
                    direction = "UP" if current_change_pct > 0 else "DOWN"
                    trigger_alert(
                        f"📈 PREMARKET GAP {direction}",
                        f"{symbol} is gapping {current_change_pct:+.2f}% to ${latest_close:.2f}!",
                    )
                    self.alerted_gaps.add(symbol)
            else:
                # 2. REGULAR TRADING HOURS: Log official open gap once, then track Day Change
                if symbol not in self.open_gap_logged:
                    logger.info(
                        f"🔔 [{symbol}] MARKET OPEN | Official Gap: {current_change_pct:+.2f}% at ${latest_close:.2f}"
                    )
                    self.open_gap_logged.add(symbol)
                gap_str = f" | Day Chg: {current_change_pct:+.2f}%"

        # Standard Info logging for regular 5m closes
        logger.info(
            f"[{symbol}] 5m Closed at {latest_time.strftime('%H:%M')} | "
            f"Close: ${latest_close:.2f}{gap_str} | 5m Vol: {latest_5m_vol:,.0f}"
        )


def subscribe_historical_bars(ib: IB, targets_dict: dict) -> dict:
    """
    Acts as a seamless drop-in replacement wrapper for the original __main__.py
    while actually instantiating the new Live Trade Tick builder.
    """
    logger.info("Initializing live tick-by-tick data streams...")
    builder = LiveTradeBarBuilder(ib, targets_dict)

    # Return the dictionary of live tickers to keep the objects alive
    return builder.start()
