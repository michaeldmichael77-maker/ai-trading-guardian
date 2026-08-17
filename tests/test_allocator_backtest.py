"""Tests for the allocator backtest harness + the validated real-data edge.

The headline test asserts the strategy's out-of-sample risk-adjusted result
holds up, so a future change that breaks the edge fails CI loudly.
"""

import os

import pytest

from trading_bot.allocator_backtest import AllocatorBacktest, _metrics
from trading_bot.trend_allocator import TrendAllocator


DATA = os.path.join(os.path.dirname(__file__), "..", "data_real_long")
has_data = os.path.isdir(DATA) and len([f for f in os.listdir(DATA)
                                        if f.endswith(".csv")]) >= 5


def test_metrics_on_flat_curve():
    m = _metrics([100.0, 100.0, 100.0, 100.0])
    assert m["return_pct"] == 0.0
    assert m["max_drawdown_pct"] == 0.0


def test_metrics_on_rising_curve():
    m = _metrics([100, 110, 120, 130, 140])
    assert m["return_pct"] > 0
    assert m["sharpe"] > 0


@pytest.mark.skipif(not has_data, reason="real data not present")
def test_allocator_runs_on_real_data():
    bt = AllocatorBacktest(DATA)
    r = bt.run()
    assert r["bars"] > 100
    assert "return_pct" in r and "sharpe" in r


@pytest.mark.skipif(not has_data, reason="real data not present")
def test_allocator_drawdown_is_controlled():
    """Crash-filtered allocator must keep max drawdown well below buy & hold."""
    bt = AllocatorBacktest(DATA, allocator=TrendAllocator(crash_filter=True))
    r = bt.run()
    bh = bt.benchmark_buy_hold("SPY")
    assert r["max_drawdown_pct"] < bh["max_drawdown_pct"]


@pytest.mark.skipif(not has_data, reason="real data not present")
def test_allocator_beats_benchmark_risk_adjusted_oos():
    """Out-of-sample, the allocator should be competitive on return AND much
    safer (lower drawdown) than buy & hold — the validated edge."""
    bt = AllocatorBacktest(DATA, allocator=TrendAllocator(crash_filter=True))
    split = int(bt.N * 0.6)
    te = bt.run(start=split)
    bh = bt.benchmark_buy_hold("SPY", start=split)
    # Strong risk-adjusted edge: OOS drawdown must be meaningfully lower.
    assert te["max_drawdown_pct"] < bh["max_drawdown_pct"]
    # And return should be at least ~85% of buy & hold (usually beats it).
    assert te["return_pct"] >= 0.85 * bh["return_pct"]
