"""Tests for the live auto-executing trend allocator."""

import pytest

from trading_bot.live_allocator import LiveAllocator
from trading_bot.trend_allocator import TrendAllocator


def _series(n=320):
    """Build a few synthetic uptrending series + a market proxy."""
    spy = [100 + i * 0.3 for i in range(n)]            # steady uptrend (market)
    aaa = [50 + i * 0.5 for i in range(n)]             # strong uptrend
    bbb = [200 - i * 0.2 for i in range(n)]            # downtrend (excluded)
    return {"SPY": spy, "AAA": aaa, "BBB": bbb}


def make(series=None, **kw):
    series = series or _series()
    alloc = TrendAllocator(trend_window=200, vol_window=40, rebalance_every=5,
                           crash_filter=True, market_symbol="SPY",
                           max_weight=0.5)
    return LiveAllocator(series, allocator=alloc, logger=lambda *_: None, **kw)


def test_enable_invests_immediately():
    la = make()
    ok, _ = la.enable()
    assert ok is True
    st = la.status()
    assert st["enabled"] is True
    # AAA is uptrending and should be held; BBB (downtrend) should not.
    held = {p["symbol"] for p in st["positions"]}
    assert "AAA" in held
    assert "BBB" not in held


def test_enable_requires_history():
    la = make(_series(n=50))   # too short for warmup
    ok, msg = la.enable()
    assert ok is False


def test_step_advances_and_rebalances():
    la = make()
    la.enable()
    start_bar = la.cursor
    for _ in range(12):
        la.step()
    assert la.cursor > start_bar
    assert la.rebalances >= 2


def test_flatten_sells_all():
    la = make()
    la.enable()
    assert len(la.status()["positions"]) > 0
    n = la.flatten()
    assert n >= 1
    assert len(la.status()["positions"]) == 0


def test_disable_stops_stepping():
    la = make()
    la.enable()
    la.disable()
    bar = la.cursor
    la.step()                  # should be a no-op when disabled
    assert la.cursor == bar


def test_crash_filter_goes_to_cash():
    # Market (SPY) in a downtrend -> allocator should hold nothing.
    n = 320
    series = {
        "SPY": [300 - i * 0.4 for i in range(n)],   # market downtrend
        "AAA": [50 + i * 0.5 for i in range(n)],    # would be up, but blocked
    }
    la = make(series)
    la.enable()
    st = la.status()
    assert len(st["positions"]) == 0
    assert st["regime"] == "RISK-OFF"


def test_status_fields_present():
    la = make()
    la.enable()
    st = la.status()
    for key in ("enabled", "regime", "equity", "return_pct", "cash",
                "positions", "rebalances", "bar", "bars_total"):
        assert key in st


def test_equity_reconciles():
    la = make()
    la.enable()
    for _ in range(20):
        la.step()
    idx = la.cursor
    prices = {s: la.series[s][idx] for s in la.symbols}
    recon = la.portfolio.balance + sum(
        pos["size"] * prices[s]
        for s, pos in la.portfolio.open_positions().items())
    assert abs(la.equity_at(idx) - recon) < 1e-6
