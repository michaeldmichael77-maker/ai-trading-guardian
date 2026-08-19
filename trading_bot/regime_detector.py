"""Market regime detection.

Classifies recent price action into one of:
  TRENDING_UP, TRENDING_DOWN, RANGING, VOLATILE
using slope of a linear fit plus realised volatility.  Pure-python, no numpy.
"""

import math


class RegimeDetector:
    def __init__(self, lookback=30):
        self.lookback = lookback

    @staticmethod
    def _linfit_slope(values):
        n = len(values)
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(values) / n
        num = sum((xs[i] - mean_x) * (values[i] - mean_y) for i in range(n))
        den = sum((xs[i] - mean_x) ** 2 for i in range(n)) or 1e-9
        return num / den

    @staticmethod
    def _returns_vol(values):
        rets = []
        for i in range(1, len(values)):
            if values[i - 1] != 0:
                rets.append((values[i] - values[i - 1]) / values[i - 1])
        if len(rets) < 2:
            return 0.0
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        return math.sqrt(var)

    def detect_regime(self, price_history):
        if len(price_history) < self.lookback:
            return "UNKNOWN"

        window = price_history[-self.lookback:]
        avg = sum(window) / len(window)
        slope = self._linfit_slope(window)
        vol = self._returns_vol(window)

        # Normalise slope to a per-bar % move relative to price level.
        norm_slope = (slope / avg) if avg else 0.0

        # High volatility dominates the classification.
        if vol > 0.004:
            return "VOLATILE"
        if norm_slope > 0.0006:
            return "TRENDING_UP"
        if norm_slope < -0.0006:
            return "TRENDING_DOWN"
        return "RANGING"
