import logging


class StrategyConfig:
    def __init__(self):
        self.ib_host = "127.0.0.1"
        self.ib_port = 7497  # Port for workstation Paper Trading
        # self.ib_port = 4002  # Make sure this matches your Paper Trading port
        self.ib_client_id = 1

        # Account & Risk Settings
        self.account_capital = 100000
        self.risk_per_trade_pct = 0.01  # 1% risk per trade

        # This allows the ATR formula enough capital headroom to actually risk the full 1%.
        self.max_position_pct = 0.20
        self.max_position_usd = 20000
        self.atr_stop_multiplier = 2.0

        # Indicator Settings
        self.sma_slow = 50
        self.ema_fast = 20
        self.volume_window = 20
        self.adx_window = 14
        self.adx_threshold = 25

        # 1 year is just enough runway for the 50-SMA and EWMA indicators to stabilize
        # before reading today's current value.
        self.lookback_duration = "1 Y"

        self._validate_risk_parameters()

    def _validate_risk_parameters(self):
        """
        ‼️ NEW: Extracted validation logic to ensure config values don't
        mathematically contradict each other before the bot attempts to trade.
        """
        if self.risk_per_trade_pct >= self.max_position_pct:
            logging.warning(
                f"‼️ WARNING: risk_per_trade_pct ({self.risk_per_trade_pct}) is "
                f"greater than or equal to max_position_pct ({self.max_position_pct}). "
                "This will artificially cap the ATR position sizing."
            )
