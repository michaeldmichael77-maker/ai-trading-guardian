"""Short-side risk-gate symmetry tests.

The most dangerous regression is one that lets a SHORT entry bypass a risk
guard that a LONG entry would respect. These tests drive the real live
``process_symbol`` path and assert that news blackout, the confidence bar and
multi-timeframe alignment gate shorts exactly like longs.
"""

import collections

import pytest

import trading_bot.api as api
from trading_bot import config


@pytest.fixture
def fresh_api(monkeypatch):
    """Reset the api module's shared state and give it a warmed buffer."""
    from trading_bot.engine.portfolio import Portfolio

    api.portfolio = Portfolio(balance=config.INITIAL_BALANCE)
    api.entry_attribution.clear()
    api.voter_attribution.clear()
    api.bot_state["last_prices"] = dict(config.SEED_PRICES)
    # Warm buffer so process_symbol passes the warmup gate.
    api.price_buffers["AAPL"] = collections.deque(
        [100.0] * config.WARMUP_TICKS, maxlen=200)

    # Force the market to return a flat price (so no stop/exit interferes).
    monkeypatch.setattr(api.market, "get_price", lambda s: 100.0)
    # Force MTF aligned by default; individual tests can override.
    monkeypatch.setattr(api.mtf, "check_alignment",
                        lambda buf: {"aligned": True, "direction": "DOWN",
                                     "timeframes": {}})
    # No news by default.
    monkeypatch.setattr(api.news_filter, "is_blackout", lambda: False)
    # Reset drawdown to NORMAL.
    api.drawdown_recovery.confidence_bonus = 0.0
    api.drawdown_recovery.risk_multiplier = 1.0
    # Start a fresh governor day so the loss-budget pre-trade guard has a sane
    # full budget (the day's loss limit is untouched).
    api.daily_governor.active = False
    api.daily_governor.start_new_day(config.INITIAL_BALANCE)
    api.portfolio.reset_daily()
    return api


def _force_decision(monkeypatch, signal, confidence):
    monkeypatch.setattr(
        api.hive_mind, "decide",
        lambda buf, regime="UNKNOWN", mtf=None, sentiment=0.0: {
            "signal": signal, "confidence": confidence,
            "reason": "forced", "votes": [], "score": 0.0,
        })


def test_short_entry_opens_when_all_gates_pass(fresh_api, monkeypatch):
    _force_decision(monkeypatch, "SELL", 0.90)
    api.process_symbol("AAPL")
    pos = api.portfolio.get_position("AAPL")
    assert pos["size"] < 0
    assert pos["side"] == "SHORT"


def test_short_entry_blocked_by_news_blackout(fresh_api, monkeypatch):
    monkeypatch.setattr(api.news_filter, "is_blackout", lambda: True)
    _force_decision(monkeypatch, "SELL", 0.90)
    api.process_symbol("AAPL")
    assert api.portfolio.get_position("AAPL")["size"] == 0


def test_long_entry_also_blocked_by_news_blackout(fresh_api, monkeypatch):
    """Symmetry check: BUY is gated the same way."""
    monkeypatch.setattr(api.news_filter, "is_blackout", lambda: True)
    _force_decision(monkeypatch, "BUY", 0.90)
    api.process_symbol("AAPL")
    assert api.portfolio.get_position("AAPL")["size"] == 0


def test_short_entry_blocked_below_confidence_bar(fresh_api, monkeypatch):
    _force_decision(monkeypatch, "SELL", 0.50)   # below MIN_CONFIDENCE
    api.process_symbol("AAPL")
    assert api.portfolio.get_position("AAPL")["size"] == 0


def test_short_entry_blocked_under_drawdown_lockdown(fresh_api, monkeypatch):
    # Lockdown raises the confidence bar; a 0.62 signal that would pass NORMAL
    # should be rejected once the bonus pushes the bar above it.
    api.drawdown_recovery.confidence_bonus = 0.15
    _force_decision(monkeypatch, "SELL", 0.62)
    api.process_symbol("AAPL")
    assert api.portfolio.get_position("AAPL")["size"] == 0


def test_short_entry_blocked_when_mtf_not_aligned(fresh_api, monkeypatch):
    monkeypatch.setattr(api.mtf, "check_alignment",
                        lambda buf: {"aligned": False, "direction": "MIXED",
                                     "timeframes": {}})
    _force_decision(monkeypatch, "SELL", 0.90)
    api.process_symbol("AAPL")
    assert api.portfolio.get_position("AAPL")["size"] == 0
