class StrategyConfig:
    def __init__(self):
        # Account & Risk Settings
        self.account_capital = 100000
        self.risk_per_trade_pct = 0.01  # 1% risk per trade
        self.atr_stop_multiplier = 2.0
        
        # Indicator Settings
        self.sma_slow = 50
        self.ema_fast = 20
        self.volume_window = 20
        self.adx_window = 14
        self.adx_threshold = 25
        
        # 1 year is just enough runway for the 50-SMA and EWMA indicators to stabilize 
        # before reading today's current value.
        self.lookback_duration = '1 Y'
