"""Exit management: per-trade stop-loss, take-profit and trailing stop.

This module centralises ALL exit decisions in one pure, easily-tested place so
the live API loop and the backtester behave identically. It is stateful only in
a small, explicit way: it tracks the peak unrealised profit of each open
position (needed for the trailing stop) keyed by symbol.

Conventions
-----------
``risk`` is the per-trade dollar stop (config.PER_TRADE_STOP_LOSS). Profit/loss
targets are expressed as multiples of that risk ("R-multiples"), so the logic
is independent of position size and price level.

``check(...)`` returns one of:
    None                  -> hold the position
    {"action": "EXIT", "reason": ...}  -> close the whole position now
"""

from trading_bot import config


class ExitManager:
    def __init__(self,
                 per_trade_stop=None,
                 take_profit_r=None,
                 trail_activate_r=None,
                 trail_giveback=None):
        self.risk = (per_trade_stop if per_trade_stop is not None
                     else config.PER_TRADE_STOP_LOSS)
        self.take_profit_r = (take_profit_r if take_profit_r is not None
                              else config.TAKE_PROFIT_R)
        self.trail_activate_r = (trail_activate_r if trail_activate_r is not None
                                 else config.TRAIL_ACTIVATE_R)
        self.trail_giveback = (trail_giveback if trail_giveback is not None
                               else config.TRAIL_GIVEBACK)
        # symbol -> peak unrealised pnl ($) seen while the position was open
        self._peak = {}
        # symbol -> per-position dollar risk (volatility-based stop set at entry).
        # Falls back to ``self.risk`` when not set, preserving old behaviour.
        self._risk = {}

    # ------------------------------------------------------------------ #
    @staticmethod
    def unrealised(position, price):
        """Signed P&L in dollars for LONG or SHORT positions."""
        size = position["size"]
        avg = position["avg_price"]
        if size == 0:
            return 0.0
        if position.get("side") == "SHORT":
            return (avg - price) * abs(size)
        return (price - avg) * size

    def on_open(self, symbol, risk_dollars=None):
        """Reset peak tracking when a new position is opened.

        ``risk_dollars`` is the dollar distance to the stop for THIS position
        (computed from volatility at entry). When omitted, the manager's default
        ``self.risk`` is used so existing callers/tests keep working unchanged.
        """
        self._peak[symbol] = 0.0
        if risk_dollars is not None and risk_dollars > 0:
            self._risk[symbol] = risk_dollars

    def on_close(self, symbol):
        self._peak.pop(symbol, None)
        self._risk.pop(symbol, None)

    def risk_for(self, symbol):
        return self._risk.get(symbol, self.risk)

    def peak(self, symbol):
        return self._peak.get(symbol, 0.0)

    # ------------------------------------------------------------------ #
    def check(self, symbol, position, price):
        """Decide whether to exit ``position`` at ``price``.

        Order of precedence: hard stop -> take-profit -> trailing stop.
        """
        if position["size"] == 0:
            return None

        # Per-position risk unit (volatility-based when set at entry).
        risk = self.risk_for(symbol)

        pnl = self.unrealised(position, price)

        # Track the running peak profit for the trailing stop.
        prev_peak = self._peak.get(symbol, 0.0)
        if pnl > prev_peak:
            prev_peak = pnl
            self._peak[symbol] = pnl

        # 1) Hard stop-loss (loss >= 1R).
        if pnl <= -risk:
            return {"action": "EXIT", "reason": "STOP-LOSS", "pnl": pnl}

        # 2) Fixed take-profit at +Nr.
        if self.take_profit_r and pnl >= self.take_profit_r * risk:
            return {"action": "EXIT", "reason": "TAKE-PROFIT", "pnl": pnl}

        # 3) Trailing stop: once profit has reached the activation threshold,
        #    exit if it gives back more than ``trail_giveback`` of its peak.
        if (self.trail_activate_r is not None
                and prev_peak >= self.trail_activate_r * risk):
            trail_level = prev_peak * (1.0 - self.trail_giveback)
            if pnl <= trail_level:
                return {"action": "EXIT", "reason": "TRAIL-STOP", "pnl": pnl}

        return None
