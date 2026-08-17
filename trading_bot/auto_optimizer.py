"""Auto optimizer.

Periodically reviews recent closed trades and nudges the Hive-Mind voter
weights toward whatever has been working.  This is a lightweight online
adaptation (reward-weighted update) rather than a heavy backtest sweep, so it
runs continuously inside the live loop without blocking.
"""

import time


class AutoOptimizer:
    def __init__(self, hive_mind, interval_seconds=30, lookback_trades=20):
        self.hive = hive_mind
        self.interval = interval_seconds
        self.lookback = lookback_trades
        self._last_run = 0.0
        self.last_report = {"runs": 0, "last_action": "idle", "weights": dict(hive_mind.weights)}
        self.runs = 0

    def maybe_optimize(self, closed_trades, attribution):
        """Run if the interval elapsed.

        attribution: dict voter_name -> running net pnl credited to that voter
        (the trade engine credits the voters that agreed with each entry).
        """
        now = time.time()
        if now - self._last_run < self.interval:
            return None
        self._last_run = now

        if len(closed_trades) < 3:
            self.last_report = {
                "runs": self.runs, "last_action": "waiting for trades",
                "weights": {k: round(v, 3) for k, v in self.hive.weights.items()},
            }
            return self.last_report

        # Reward-weighted nudge based on attribution.
        total = sum(abs(v) for v in attribution.values()) or 1.0
        for name, weight in self.hive.weights.items():
            credit = attribution.get(name, 0.0)
            # Normalised reward in roughly [-1, 1].
            reward = credit / total
            new_w = weight * (1 + 0.08 * reward)
            # Clamp to keep the swarm balanced.
            self.hive.weights[name] = max(0.4, min(2.0, new_w))

        self.runs += 1
        self.last_report = {
            "runs": self.runs,
            "last_action": f"adjusted weights @ {time.strftime('%H:%M:%S')}",
            "weights": {k: round(v, 3) for k, v in self.hive.weights.items()},
        }
        return self.last_report

    def status(self):
        return self.last_report
