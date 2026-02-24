from ib_insync import LimitOrder, MarketOrder, Stock
from ib_insync import IB
import logging

from account import verify_paper_account, verify_cash_account


def on_fill_event(trade, fill):
    """
    ‼️ NEW: Callback to handle partial or full fills.
    Extracted this logic to ensure we get clear, event-driven logging on order execution states.
    """
    status = "PARTIAL FILL" if trade.orderStatus.remaining > 0 else "FULL FILL"
    logging.info(
        f"‼️ {status}: {fill.execution.side} {fill.execution.shares} shares of {trade.contract.symbol} @ {fill.execution.price}"
    )
    logging.info(f"‼️ Remaining to fill: {trade.orderStatus.remaining} shares")


def get_pending_shares(ib, symbol, action):
    """
    ‼️ NEW: Extracted helper to calculate how many shares are currently tied up in open orders.
    This is critical for preventing duplicate orders when partial fills happen.
    """
    pending_shares = 0.0
    for trade in ib.openTrades():
        if trade.contract.symbol == symbol and trade.order.action == action:
            remaining = trade.order.totalQuantity - trade.orderStatus.filled
            if remaining > 0:
                pending_shares += remaining
    return pending_shares


def get_available_funds(ib):
    """Returns the available cash in the account for trading."""
    account_values = ib.accountValues()
    for val in account_values:
        if val.tag == "AvailableFunds" and val.currency == "USD":
            return float(val.value)
    return 0.0


def get_current_positions(ib):
    """Returns a dictionary of {symbol: quantity} for current open positions."""
    positions = ib.positions()
    current_holdings = {}
    for p in positions:
        if p.position != 0:
            current_holdings[p.contract.symbol] = p.position
    return current_holdings


def execute_limit_order(ib, symbol, action, quantity, price):
    """Executes a live limit order."""

    limit_price = round(float(price), 2)

    print(
        f"‼️ TRANSMITTING ORDER: {action} {quantity} shares of {symbol} at Limit ${limit_price}"
    )
    contract = Stock(symbol, "SMART", "USD")
    ib.qualifyContracts(contract)
    order = LimitOrder(action, quantity, limit_price)
    trade = ib.placeOrder(contract, order)

    trade.fillEvent += on_fill_event

    return trade


def execute_market_order(ib, symbol, action, quantity):
    """Executes a live market order."""
    print(f"TRANSMITTING ORDER: {action} {quantity} shares of {symbol} at Market Price")
    contract = Stock(symbol, "SMART", "USD")
    ib.qualifyContracts(contract)
    order = MarketOrder(action, quantity)
    trade = ib.placeOrder(contract, order)

    trade.fillEvent += on_fill_event

    return trade


def ensure_connection(ib: IB, config):
    """Checks if the broker connection is alive, and forces a reconnect if it's dead."""
    if ib.isConnected():
        return

    logging.warning("Broker connection lost or not started. Attempting to connect...")

    while not ib.isConnected():
        try:
            ib.connect(config.ib_host, config.ib_port, clientId=config.ib_client_id)
            logging.info("Successfully connected to Interactive Brokers.")

            verify_paper_account(ib)
            verify_cash_account(ib)

        except ConnectionRefusedError:
            logging.error(
                "Connection refused. Is TWS or IB Gateway running? Retrying in 60 seconds..."
            )

            ib.sleep(60)
        except Exception as e:
            logging.error(
                f"Unexpected connection error: {e}. Retrying in 60 seconds..."
            )

            ib.sleep(60)
