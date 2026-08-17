"""Sentiment overlay.

Maintains a slowly mean-reverting market sentiment score in [-1, 1] per symbol
(and an aggregate).  The strategy uses it as a soft tilt: strong agreement
boosts confidence, disagreement dampens it.  Simulated, but structured so a
real feed (social, options flow, put/call) could be dropped in.
"""

import random


class SentimentOverlay:
    def __init__(self, symbols=None, seed=None):
        self._rng = random.Random(seed)
        self.symbols = symbols or []
        self.scores = {s: 0.0 for s in self.symbols}
        self.aggregate = 0.0

    def update(self, symbol):
        cur = self.scores.get(symbol, 0.0)
        # Mean-reverting random walk towards 0.
        drift = -cur * 0.05
        shock = self._rng.gauss(0, 0.08)
        new = max(-1.0, min(1.0, cur + drift + shock))
        self.scores[symbol] = new
        if self.scores:
            self.aggregate = sum(self.scores.values()) / len(self.scores)
        return new

    def get(self, symbol):
        return self.scores.get(symbol, 0.0)

    def label(self, score=None):
        s = self.aggregate if score is None else score
        if s > 0.3:
            return "BULLISH"
        if s < -0.3:
            return "BEARISH"
        return "NEUTRAL"

    def status(self):
        return {
            "aggregate": round(self.aggregate, 3),
            "label": self.label(),
            "per_symbol": {k: round(v, 3) for k, v in self.scores.items()},
        }
