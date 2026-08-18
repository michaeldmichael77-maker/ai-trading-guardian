"""Market data simulator.

Generates realistic-looking price action using a geometric-random-walk with
gentle mean-reverting drift and occasional regime shifts.  This lets the whole
system run with zero external dependencies / API keys while still exercising
the regime detector, multi-timeframe logic and strategy ensemble.
"""

import random
import time

from trading_bot import config


class MarketSimulator:
    def __init__(self, seed=None):
        self._rng = random.Random(seed)
        self.prices = dict(config.SEED_PRICES)
        # Each symbol carries a slow-moving "drift" that periodically flips,
        # producing trends, ranges and reversals for the regime detector.
        self._drift = {s: self._rng.uniform(-1, 1) * 0.0002 for s in config.SYMBOLS}
        self._drift_age = {s: 0 for s in config.SYMBOLS}
        self._last_tick = time.time()

    def add_symbol(self, symbol, start_price):
        """Register a brand-new symbol at runtime so it can be traded live."""
        if symbol in self.prices:
            return False
        self.prices[symbol] = float(start_price)
        self._drift[symbol] = self._rng.uniform(-1, 1) * 0.0002
        self._drift_age[symbol] = 0
        return True

    def _evolve_drift(self, symbol):
        self._drift_age[symbol] += 1
        # Flip / reshape the drift roughly every 40-120 ticks.
        if self._drift_age[symbol] > self._rng.randint(40, 120):
            self._drift[symbol] = self._rng.uniform(-1, 1) * 0.0004
            self._drift_age[symbol] = 0

    def get_price(self, symbol):
        """Advance the price for ``symbol`` one tick and return it."""
        if symbol not in self.prices:
            return None

        self._evolve_drift(symbol)
        vol = config.SYMBOL_VOL.get(symbol, 0.0015)
        shock = self._rng.gauss(0, 1) * vol
        drift = self._drift[symbol]
        change = drift + shock

        new_price = self.prices[symbol] * (1 + change)
        # Keep prices sane / positive.
        new_price = max(new_price, 0.01)
        self.prices[symbol] = new_price
        return round(new_price, 4)

    def snapshot(self):
        """Return current price for every symbol (without advancing)."""
        return {s: round(p, 4) for s, p in self.prices.items()}
