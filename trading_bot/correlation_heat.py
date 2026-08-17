"""Portfolio heat & correlation monitor.

"Heat" = fraction of account equity currently exposed to risk.  We also flag
correlation risk when too many open positions live in the same correlation
cluster (e.g. four crypto longs all behave like one big position).
"""

from trading_bot import config


class PortfolioHeatMonitor:
    def __init__(self, max_heat=config.MAX_PORTFOLIO_HEAT):
        self.max_heat = max_heat
        self.current_heat = 0.0
        self.correlation_risk = "LOW"

    @staticmethod
    def _group_of(symbol):
        for group, members in config.CORRELATION_GROUPS.items():
            if symbol in members:
                return group
        return "OTHER"

    def compute(self, open_positions, equity, per_trade_stop):
        """open_positions: dict symbol -> position dict with 'size','avg_price'."""
        if equity <= 0:
            equity = 1.0

        # Heat: assume each open position risks up to the per-trade stop.
        risk_dollars = len(open_positions) * per_trade_stop
        self.current_heat = round(risk_dollars / equity, 4)

        # Correlation clustering.
        group_counts = {}
        for symbol in open_positions:
            g = self._group_of(symbol)
            group_counts[g] = group_counts.get(g, 0) + 1

        max_cluster = max(group_counts.values()) if group_counts else 0
        if max_cluster >= 4:
            self.correlation_risk = "HIGH"
        elif max_cluster == 3:
            self.correlation_risk = "MEDIUM"
        else:
            self.correlation_risk = "LOW"

        return {
            "heat": self.current_heat,
            "heat_pct": round(self.current_heat * 100, 2),
            "max_heat_pct": round(self.max_heat * 100, 2),
            "correlation_risk": self.correlation_risk,
            "group_counts": group_counts,
        }

    def can_add_position(self, open_positions, equity, per_trade_stop, symbol):
        """Return (allowed: bool, reason: str)."""
        if len(open_positions) >= config.MAX_OPEN_POSITIONS:
            return False, "Max open positions reached"

        projected_risk = (len(open_positions) + 1) * per_trade_stop
        if equity > 0 and (projected_risk / equity) > self.max_heat:
            return False, "Portfolio heat limit"

        # Block over-concentration in one correlation group.
        group = self._group_of(symbol)
        same_group = sum(1 for s in open_positions if self._group_of(s) == group)
        if same_group >= 3:
            return False, f"Correlation cluster cap ({group})"

        return True, "OK"
