"""Execution quality tracking.

Tracks slippage, simulated fill latency and effective spread for every order so
the dashboard can show whether the system is getting good fills.  In a live
broker integration these would be measured against the NBBO at order time.
"""

import random
import time


class ExecutionQualityTracker:
    def __init__(self, seed=None):
        self._rng = random.Random(seed)
        self.fills = []
        self.total_slippage = 0.0
        self.total_orders = 0

    def record_fill(self, symbol, intended_price, side):
        """Simulate a realistic fill around the intended price and log quality."""
        # Slippage: usually a few bps, occasionally worse.
        bps = abs(self._rng.gauss(0, 1.5))
        slip_frac = bps / 10_000.0
        # Buys tend to fill slightly higher, sells slightly lower.
        direction = 1 if side == "BUY" else -1
        fill_price = intended_price * (1 + direction * slip_frac)

        slippage_dollars = abs(fill_price - intended_price)
        latency_ms = round(self._rng.uniform(8, 65), 1)
        spread_bps = round(abs(self._rng.gauss(1.0, 0.6)), 2)

        record = {
            "symbol": symbol,
            "side": side,
            "intended": round(intended_price, 4),
            "fill": round(fill_price, 4),
            "slippage_bps": round(bps, 2),
            "slippage_dollars": round(slippage_dollars, 4),
            "latency_ms": latency_ms,
            "spread_bps": spread_bps,
            "time": time.time(),
        }
        self.fills.insert(0, record)
        self.fills = self.fills[:50]
        self.total_slippage += bps
        self.total_orders += 1
        return record

    def summary(self):
        if not self.total_orders:
            return {
                "avg_slippage_bps": 0.0,
                "avg_latency_ms": 0.0,
                "fill_count": 0,
                "quality_score": 100.0,
            }
        avg_slip = self.total_slippage / self.total_orders
        avg_latency = sum(f["latency_ms"] for f in self.fills) / len(self.fills)
        # 0 bps slippage -> 100; ~5 bps -> ~50.
        quality = max(0.0, 100.0 - avg_slip * 10.0)
        return {
            "avg_slippage_bps": round(avg_slip, 2),
            "avg_latency_ms": round(avg_latency, 1),
            "fill_count": self.total_orders,
            "quality_score": round(quality, 1),
            "recent_fills": self.fills[:8],
        }
