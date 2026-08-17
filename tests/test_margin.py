"""Gross-exposure / buying-power (leverage) tests.

Shorts credit cash but still create real exposure, so the system must cap total
|notional| (long + short) against equity * MAX_GROSS_LEVERAGE. Without this a
basket of shorts could grow unbounded while cash/equity still looked healthy.
"""

import collections

import pytest

import trading_bot.api as api
from trading_bot import config
from trading_bot.engine.portfolio import Portfolio


# --------------------------------------------------------------------------- #
# Portfolio.gross_exposure
# --------------------------------------------------------------------------- #
def test_gross_exposure_counts_both_sides():
    p = Portfolio(balance=100_000.0)
    p.execute_buy("AAPL", 100.0, 10)     # +1,000 notional
    p.execute_short("TSLA", 200.0, 5)    # 1,000 notional (abs)
    gross = p.gross_exposure({"AAPL": 100.0, "TSLA": 200.0})
    assert gross == 2_000.0


def test_gross_exposure_uses_current_price():
    p = Portfolio(balance=100_000.0)
    p.execute_short("AAPL", 100.0, 10)
    # price moves to 120 -> exposure grows to 1,200
    assert p.gross_exposure({"AAPL": 120.0}) == 1_200.0


# --------------------------------------------------------------------------- #
# Live buying_power_ok gate
# --------------------------------------------------------------------------- #
@pytest.fixture
def fresh(monkeypatch):
    api.portfolio = Portfolio(balance=100_000.0)
    api.bot_state["last_prices"] = {"AAPL": 100.0, "TSLA": 200.0}
    return api


def test_buying_power_ok_allows_within_cap(fresh):
    # Flat book: a 1,000 notional entry is well under 1.5x * 100k.
    assert api.buying_power_ok("AAPL", 100.0, 10) is True


def test_buying_power_blocks_over_cap(fresh, monkeypatch):
    # Pretend we already hold near the leverage ceiling.
    api.portfolio.execute_buy("AAPL", 100.0, 1490)   # 149,000 gross
    # equity ~= 100k (bought at current price), cap = 150k.
    # Another 2,000 notional would push to 151,000 > 150,000.
    assert api.buying_power_ok("TSLA", 200.0, 10) is False


def test_buying_power_blocks_when_equity_nonpositive(fresh):
    api.bot_state["last_prices"] = {"AAPL": 100.0}
    api.portfolio.balance = 0.0
    assert api.buying_power_ok("AAPL", 100.0, 10) is False


# --------------------------------------------------------------------------- #
# End-to-end: leverage stays bounded across a full backtest
# --------------------------------------------------------------------------- #
def test_backtest_respects_gross_leverage_cap():
    from trading_bot.backtest import Backtester
    bt = Backtester(seed=42)
    worst_lev = 0.0
    for _ in range(500):
        prices = {}
        for sym in bt.symbols:
            p = bt.market.get_price(sym)
            prices[sym] = p
            bt.buffers[sym].append(p)
            if len(bt.buffers[sym]) > 200:
                bt.buffers[sym].pop(0)
            bt.sentiment.update(sym)
            bt._step_symbol(sym, p)
        eq = bt.portfolio.equity(prices)
        gross = bt.portfolio.gross_exposure(prices)
        if eq > 0:
            worst_lev = max(worst_lev, gross / eq)
    # Allow a little slack: the cap is enforced at entry; existing positions
    # can drift slightly as prices move after entry.
    assert worst_lev <= config.MAX_GROSS_LEVERAGE * 1.25
