"""Tests for the validated TrendAllocator engine."""

import math

from trading_bot.trend_allocator import (
    TrendAllocator, moving_average, volatility)


def _uptrend(n=260, start=100.0, step=0.5):
    return [start + i * step for i in range(n)]


def _downtrend(n=260, start=200.0, step=0.5):
    return [start - i * step for i in range(n)]


# --------------------------------------------------------------------------- #
# Indicators
# --------------------------------------------------------------------------- #
def test_moving_average_none_before_window():
    assert moving_average([1, 2, 3], 1, 5) is None


def test_moving_average_value():
    assert moving_average([1, 2, 3, 4, 5], 4, 5) == 3.0


def test_volatility_positive():
    series = [100 * (1.01 ** i) for i in range(50)]
    assert volatility(series, 49, 20) > 0


# --------------------------------------------------------------------------- #
# Core rules
# --------------------------------------------------------------------------- #
def test_uptrend_is_investable():
    a = TrendAllocator(trend_window=200, vol_window=40, crash_filter=False)
    series = {"AAA": _uptrend()}
    inv = a.investable(series, len(series["AAA"]) - 1)
    assert "AAA" in inv


def test_downtrend_is_not_investable():
    a = TrendAllocator(trend_window=200, vol_window=40, crash_filter=False)
    series = {"AAA": _downtrend()}
    inv = a.investable(series, len(series["AAA"]) - 1)
    assert "AAA" not in inv


def test_crash_filter_blocks_everything_when_market_down():
    a = TrendAllocator(trend_window=200, vol_window=40, crash_filter=True,
                       market_symbol="SPY")
    series = {"SPY": _downtrend(), "AAA": _uptrend()}
    idx = len(series["AAA"]) - 1
    # Even though AAA is up, SPY (the market) is down -> go to cash.
    assert a.investable(series, idx, market_series=series["SPY"]) == []


def test_crash_filter_allows_when_market_up():
    a = TrendAllocator(trend_window=200, vol_window=40, crash_filter=True,
                       market_symbol="SPY")
    series = {"SPY": _uptrend(), "AAA": _uptrend()}
    idx = len(series["AAA"]) - 1
    inv = a.investable(series, idx, market_series=series["SPY"])
    assert "AAA" in inv


# --------------------------------------------------------------------------- #
# Weights
# --------------------------------------------------------------------------- #
def test_weights_sum_to_at_most_one():
    a = TrendAllocator(trend_window=200, vol_window=40, crash_filter=False)
    series = {"AAA": _uptrend(), "BBB": _uptrend(start=50, step=0.3)}
    idx = len(series["AAA"]) - 1
    w = a.target_weights(series, idx)
    assert 0 < sum(w.values()) <= 1.0 + 1e-9


def test_lower_vol_gets_higher_weight():
    a = TrendAllocator(trend_window=200, vol_window=40, crash_filter=False,
                       max_weight=1.0)
    # calm asset (small steps) vs choppy asset (zig-zag) — both uptrending
    calm = [100 + i * 0.5 for i in range(260)]
    choppy = [100 + i * 0.5 + (5 if i % 2 else -5) for i in range(260)]
    series = {"CALM": calm, "CHOP": choppy}
    idx = 259
    w = a.target_weights(series, idx)
    assert w["CALM"] > w["CHOP"]


def test_no_investable_returns_empty_weights():
    a = TrendAllocator(trend_window=200, vol_window=40, crash_filter=False)
    series = {"AAA": _downtrend()}
    assert a.target_weights(series, 259) == {}


def test_max_weight_cap():
    a = TrendAllocator(trend_window=200, vol_window=40, crash_filter=False,
                       max_weight=0.35)
    series = {f"S{i}": _uptrend(start=100 + i) for i in range(5)}
    idx = 259
    w = a.target_weights(series, idx)
    assert all(v <= 0.35 + 1e-9 for v in w.values())


def test_rebalance_cadence():
    a = TrendAllocator(rebalance_every=5)
    assert a.should_rebalance(10) is True
    assert a.should_rebalance(11) is False
