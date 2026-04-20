import logging
import pandas as pd
from ib_insync import IB, Stock, util
from .alerts import trigger_alert

logger = logging.getLogger("ibkr_alerts")

def create_bar_handler(targets_dict: dict):
    """Factory function to create a closure that holds the target dictionaries."""
    
    def on_bar_update(bars, hasNewBar):
        """Callback function triggered when a new bar updates or closes."""
        # ONLY run the heavy Pandas logic if a 5-minute candle has officially closed
        if hasNewBar:
            symbol = bars.contract.symbol

            # Convert the ib_insync bars to a Pandas DataFrame
            df = util.df(bars)
            df.set_index("date", inplace=True)

            # Resample to 30 minutes
            ohlcv_dict = {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
            df_30m = df.resample("30min").agg(ohlcv_dict).dropna()
            
            if df_30m.empty:
                return

            latest_30m = df_30m.iloc[-1]
            latest_volume = latest_30m['volume']
            latest_close = latest_30m['close']
            
            # Fetch specific targets for this symbol
            symbol_targets = targets_dict.get(symbol, {})
            t_vol = symbol_targets.get('target_volume')
            t_buy = symbol_targets.get('target_buy')
            t_sell = symbol_targets.get('target_sell')

            # Standard Info logging for regular 30m closes
            logger.info(f"[{symbol}] 30m Closed | Close: ${latest_close:.2f} | Vol: {latest_volume:,.0f}")

            # --- ALERT LOGIC ---
            if t_vol and latest_volume >= t_vol:
                trigger_alert("🚨 VOLUME SURGE", f"{symbol} volume ({latest_volume:,.0f}) exceeded target ({t_vol:,.0f})!")
                
            if t_buy and latest_close <= t_buy:
                trigger_alert("💸 BUY TARGET REACHED", f"{symbol} dropped to ${latest_close:.2f} (Target: ${t_buy:.2f})!")

            if t_sell and latest_close >= t_sell:
                trigger_alert("💰 SELL TARGET REACHED", f"{symbol} climbed to ${latest_close:.2f} (Target: ${t_sell:.2f})!")

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
            durationStr="900 S",
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
        ib.sleep(2) # Stagger requests

    return live_bars
