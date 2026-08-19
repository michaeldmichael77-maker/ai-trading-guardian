"""Broker adapters.

A ``BrokerAdapter`` is a thin, swappable layer between the trading engine and a
real (or simulated) brokerage. The rest of the system never talks to a broker
directly — it goes through this interface — so the simulator and a real broker
like Alpaca are interchangeable, and every safety rail keeps working unchanged.
"""

from trading_bot.brokers.base import BrokerAdapter, BrokerError

__all__ = ["BrokerAdapter", "BrokerError"]
