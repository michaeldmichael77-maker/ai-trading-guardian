"""Volatility estimation for risk-based position sizing.

The original system used a hard-coded per-tick volatility constant, which is
only valid at ~1-second resolution. On daily bars that constant is ~20x too
small, so positions were sized ~20x too large and a nominal "$50 stop" produced
$800+ losses when a daily bar gapped through it.

This module measures volatility directly from the price series, so position
sizing automatically adapts to whatever bar granularity the data actually has
(1s ticks, 1m, 1h, daily). That is the core fix that makes losses bounded and
consistent on real data.

We expose two estimators:

* ``realized_sigma(closes, window)`` - stdev of close-to-close returns
  (fraction of price). Works when only closes are available (our tick buffers).
* ``atr(highs, lows, closes, window)`` - classic Average True Range in price
  units, used when OHLC is available (CSV / real data).

``expected_move(...)`` returns the per-bar expected dollar move per unit, which
is what position sizing divides risk-dollars by.
"""

import math


def realized_sigma(closes, window=20):
    """Stdev of close-to-close returns over ``window`` (as a fraction)."""
    if len(closes) < 3:
        return 0.0
    series = closes[-(window + 1):]
    rets = []
    for i in range(1, len(series)):
        prev = series[i - 1]
        if prev:
            rets.append((series[i] - prev) / prev)
    if len(rets) < 2:
        return 0.0
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var)


def atr(highs, lows, closes, window=14):
    """Average True Range in price units (needs OHLC history)."""
    n = min(len(highs), len(lows), len(closes))
    if n < 2:
        return 0.0
    trs = []
    for i in range(1, n):
        high, low, prev_close = highs[i], lows[i], closes[i - 1]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    if not trs:
        return 0.0
    window = min(window, len(trs))
    return sum(trs[-window:]) / window


def expected_move(closes, price, window=20, floor_frac=0.0005):
    """Per-bar expected dollar move for one unit of the instrument.

    Uses realized return-volatility scaled by the current price. A small floor
    prevents division blow-ups during dead-flat periods.
    """
    sigma = realized_sigma(closes, window=window)
    move = sigma * price
    floor = floor_frac * price
    return max(move, floor)
