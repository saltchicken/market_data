import logging
import datetime
import pandas as pd
from ib_insync import IB, Stock, util
from .alerts import trigger_alert

logger = logging.getLogger("ibkr_alerts")


def create_bar_handler(targets_dict: dict):
    """Factory function to create a closure that holds the target dictionaries."""

    # State trackers for debouncing alerts
    alerted_gaps = set()
    open_gap_logged = set()
    alerted_volume = set()
    alerted_buy = set()
    alerted_sell = set()

    def on_bar_update(bars, hasNewBar):
        """Callback function triggered when a new bar updates or closes."""
        if hasNewBar:
            symbol = bars.contract.symbol

            # Convert the ib_insync bars to a Pandas DataFrame
            df = util.df(bars)
            df.set_index("date", inplace=True)

            # NOTE: Drop the currently forming (live) candle.
            # We only evaluate fully closed 5-minute candles.
            closed_df = df.iloc[:-1]
            
            if closed_df.empty:
                return

            # --- 1. Extract the Latest 5-Minute Closed Candle ---
            latest_5m = closed_df.iloc[-1]
            latest_time = closed_df.index[-1].time()
            latest_close = latest_5m["close"]
            latest_5m_vol = latest_5m["volume"]

            market_open_time = datetime.time(6, 30) # Assumes PST/PDT

            # --- 2. Resample to Track the 30-Minute Bucket ---
            ohlcv_dict = {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
            df_30m = closed_df.resample("30min").agg(ohlcv_dict).dropna()

            if df_30m.empty:
                return

            # This bucket is "live" and filling up until the :25 or :55 candle closes
            current_30m_bucket = df_30m.iloc[-1]
            current_30m_vol = current_30m_bucket["volume"]

            # Fetch specific targets and the previous day's close for this symbol
            symbol_targets = targets_dict.get(symbol, {})
            t_vol = symbol_targets.get("target_volume")
            t_buy = symbol_targets.get("target_buy")
            t_sell = symbol_targets.get("target_sell")
            prev_close = symbol_targets.get("prev_close")

            # --- PREMARKET GAP & MARKET OPEN CALCULATION ---
            gap_str = ""
            if prev_close and prev_close > 0:
                current_change_pct = ((latest_close - prev_close) / prev_close) * 100

                if latest_time < market_open_time:
                    # 1. PREMARKET: Log as Pre-Gap and check for extreme alerts
                    gap_str = f" | Pre-Gap: {current_change_pct:+.2f}%"

                    if abs(current_change_pct) >= 5.0 and symbol not in alerted_gaps:
                        direction = "UP" if current_change_pct > 0 else "DOWN"
                        trigger_alert(
                            f"📈 PREMARKET GAP {direction}",
                            f"{symbol} is gapping {current_change_pct:+.2f}% to ${latest_close:.2f}!",
                        )
                        alerted_gaps.add(symbol)
                else:
                    # 2. REGULAR TRADING HOURS: Log official open gap once, then track Day Change
                    if symbol not in open_gap_logged:
                        logger.info(
                            f"🔔 [{symbol}] MARKET OPEN | Official Gap: {current_change_pct:+.2f}% at ${latest_close:.2f}"
                        )
                        open_gap_logged.add(symbol)

                    gap_str = f" | Day Chg: {current_change_pct:+.2f}%"

            # Standard Info logging for regular 5m closes
            logger.info(
                f"[{symbol}] 5m Closed at {latest_time.strftime('%H:%M')} | Close: ${latest_close:.2f}{gap_str} | 5m Vol: {latest_5m_vol:,.0f}"
            )

            # --- TARGET ALERTS (Evaluated every 5 mins) ---
            
            # Volume Alert: Early Warning System against the cumulative 30m target
            if t_vol and current_30m_vol >= t_vol and symbol not in alerted_volume:
                trigger_alert(
                    "🚨 VOLUME SURGE",
                    f"{symbol} 30m running volume ({current_30m_vol:,.0f}) exceeded target ({t_vol:,.0f}) early at {latest_time.strftime('%H:%M')}!",
                )
                alerted_volume.add(symbol)

            # Price Alerts: Evaluated immediately on the 5m close to reduce slippage
            if t_buy and latest_close <= t_buy and symbol not in alerted_buy:
                trigger_alert(
                    "💸 BUY TARGET REACHED",
                    f"{symbol} dropped to ${latest_close:.2f} (Target: ${t_buy:.2f})!",
                )
                alerted_buy.add(symbol)

            if t_sell and latest_close >= t_sell and symbol not in alerted_sell:
                trigger_alert(
                    "💰 SELL TARGET REACHED",
                    f"{symbol} climbed to ${latest_close:.2f} (Target: ${t_sell:.2f})!",
                )
                alerted_sell.add(symbol)

            # --- OFFICIAL 30-MINUTE BUCKET LOGGING ---
            # A 30m bucket is only fully complete when the 5m candle stamped at xx:25 or xx:55 closes.
            if latest_time.minute in (25, 55):
                logger.info(
                    f"📦 [{symbol}] 30m BUCKET COMPLETE | End Close: ${current_30m_bucket['close']:.2f} | Total 30m Vol: {current_30m_vol:,.0f}"
                )

    return on_bar_update


def subscribe_historical_bars(ib: IB, targets_dict: dict) -> dict:
    """Qualify contracts and stagger the historical data requests."""
    symbols = list(targets_dict.keys())
    contracts = [Stock(symbol, "SMART", "USD") for symbol in symbols]
    ib.qualifyContracts(*contracts)

    live_bars = {}
    logger.info("Initializing historical data requests for PREMARKET...")

    # Generate our specific callback handler injected with the targets
    bar_handler = create_bar_handler(targets_dict)

    for contract in contracts:
        bars = ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr="1 D",  # Pull 1 day of history to prevent data starvation on the 30m volume
            barSizeSetting="5 mins",
            whatToShow="TRADES",
            useRTH=False,  # CRITICAL: False allows premarket/after-hours data
            keepUpToDate=True,
        )

        # Attach the event handler
        bars.updateEvent += bar_handler

        # Store in our dictionary to keep the reference alive
        live_bars[contract.symbol] = bars

        logger.info(f"Subscribed to {contract.symbol}")
        ib.sleep(2)  # Stagger requests

    return live_bars
