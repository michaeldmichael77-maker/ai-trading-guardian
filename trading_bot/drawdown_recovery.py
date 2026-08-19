"""Drawdown recovery controller.

When the account draws down, we throttle risk (smaller size, higher confidence
bar) until equity recovers.  This implements a simple three-tier de-risking
ladder plus a recovery mode that gradually restores normal sizing.
"""


class DrawdownRecovery:
    def __init__(self, soft=0.02, medium=0.04, hard=0.06):
        # Drawdown thresholds as fraction of peak equity.
        self.soft = soft
        self.medium = medium
        self.hard = hard
        self.mode = "NORMAL"
        self.risk_multiplier = 1.0
        self.confidence_bonus = 0.0

    def update(self, equity, peak_equity):
        if peak_equity <= 0:
            dd = 0.0
        else:
            dd = max(0.0, (peak_equity - equity) / peak_equity)

        if dd >= self.hard:
            self.mode = "LOCKDOWN"
            self.risk_multiplier = 0.25
            self.confidence_bonus = 0.15
        elif dd >= self.medium:
            self.mode = "DEFENSIVE"
            self.risk_multiplier = 0.5
            self.confidence_bonus = 0.08
        elif dd >= self.soft:
            self.mode = "CAUTIOUS"
            self.risk_multiplier = 0.75
            self.confidence_bonus = 0.04
        else:
            self.mode = "NORMAL"
            self.risk_multiplier = 1.0
            self.confidence_bonus = 0.0

        return {
            "mode": self.mode,
            "drawdown_pct": round(dd * 100, 2),
            "risk_multiplier": self.risk_multiplier,
            "confidence_bonus": self.confidence_bonus,
        }
