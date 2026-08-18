"""Guardian: real-time risk supervisor sitting in front of the portfolio.

The Guardian is the last line of defence before/while a position is live.  It
checks per-trade stop-losses, portfolio-level exposure and produces a single
risk verdict the rest of the system can trust.
"""

from trading_bot import config


class Guardian:
    def __init__(self, portfolio, per_trade_stop=config.PER_TRADE_STOP_LOSS):
        self.portfolio = portfolio
        self.per_trade_stop = per_trade_stop
        self.risk_status = "OK"
        self.alerts = []

    def check_per_trade_stops(self, price_map):
        """Return list of symbols whose loss breached the per-trade stop."""
        breached = []
        for symbol, pos in self.portfolio.open_positions().items():
            price = price_map.get(symbol, pos["avg_price"])
            loss = (pos["avg_price"] - price) * pos["size"]  # +ve = loss for long
            if loss >= self.per_trade_stop:
                breached.append(symbol)
        return breached

    def assess(self, price_map):
        """Produce an overall risk verdict for the dashboard."""
        unrealised = self.portfolio.unrealised_pnl(price_map)
        open_count = self.portfolio.position_count()

        status = "OK"
        if open_count >= config.MAX_OPEN_POSITIONS:
            status = "ELEVATED"
        if unrealised <= -(self.per_trade_stop * 2):
            status = "ELEVATED"
        if unrealised <= -(config.MAX_DAILY_LOSS * 0.75):
            status = "HIGH"

        self.risk_status = status
        return {
            "risk_status": status,
            "unrealised_pnl": round(unrealised, 2),
            "open_positions": open_count,
        }
