"""Daily Governor.

Owns the *daily* trading session: it enforces the hard profit target, the
maximum daily loss and per-trade stop levels, tracks every position opened
during the day and decides when the day must end.
"""

import time
from dataclasses import dataclass

from trading_bot import config


@dataclass
class DailyLimits:
    max_profit: float = config.MAX_DAILY_PROFIT
    max_loss: float = config.MAX_DAILY_LOSS
    per_trade_stop_loss: float = config.PER_TRADE_STOP_LOSS


class DailyGovernor:
    def __init__(self, limits: DailyLimits):
        self.limits = limits
        self.active = False
        self.day_start_balance = None
        self.current_pnl = 0.0
        self.shutdown_reason = None
        self.session_start = None
        self.session_end = None
        # symbol -> entry record opened this session
        self.positions = {}
        self.trades_today = 0

    # ------------------------------------------------------------------ #
    # Session lifecycle
    # ------------------------------------------------------------------ #
    def start_new_day(self, starting_balance):
        if self.active:
            return False
        self.active = True
        self.day_start_balance = starting_balance
        self.current_pnl = 0.0
        self.shutdown_reason = None
        self.session_start = time.time()
        self.session_end = None
        self.positions = {}
        self.trades_today = 0
        return True

    def end_day(self, reason="Day ended"):
        self.active = False
        self.shutdown_reason = reason
        self.session_end = time.time()

    def get_shutdown_reason(self):
        return self.shutdown_reason or "Day has not been started or already ended."

    # ------------------------------------------------------------------ #
    # Position tracking
    # ------------------------------------------------------------------ #
    def register_position(self, symbol, price, size, side):
        self.positions[symbol] = {
            "entry": price,
            "size": size,
            "side": side,
            "time": time.time(),
        }
        self.trades_today += 1

    def close_position(self, symbol):
        self.positions.pop(symbol, None)

    # ------------------------------------------------------------------ #
    # P&L / limit evaluation
    # ------------------------------------------------------------------ #
    def update_pnl(self, current_balance):
        """Update P&L from current mark-to-market equity and evaluate limits.

        Returns the limit verdict dict (see ``_evaluate_limits``) so the caller
        can react immediately (e.g. flatten positions / send alerts).
        """
        if self.day_start_balance is None:
            return {"breach": None}
        self.current_pnl = current_balance - self.day_start_balance
        return self._evaluate_limits()

    def _evaluate_limits(self):
        """Evaluate hard limits. Returns a verdict describing any breach.

        verdict["breach"] is one of: None, "PROFIT", "LOSS".
        The LOSS check uses a small safety buffer so we halt as we *approach*
        the limit rather than only after blowing through it on a fast move —
        making the configured max daily loss an effective hard ceiling.
        """
        verdict = {"breach": None, "pnl": self.current_pnl}
        if not self.active:
            return verdict

        # Hard profit target.
        if self.current_pnl >= self.limits.max_profit:
            verdict["breach"] = "PROFIT"
            self.end_day(
                f"Daily profit target reached (+${self.current_pnl:,.2f})"
            )
            return verdict

        # Hard loss limit (with safety buffer). We stop slightly BEFORE the
        # absolute limit so that even with slippage on the flattening orders the
        # realised daily loss stays at or under the configured maximum.
        buffer = getattr(config, "DAILY_LOSS_SAFETY_BUFFER", 0.90)
        soft_loss_trigger = abs(self.limits.max_loss) * buffer
        if self.current_pnl <= -soft_loss_trigger:
            verdict["breach"] = "LOSS"
            self.end_day(
                f"Daily loss limit reached (-${abs(self.current_pnl):,.2f} "
                f"of ${abs(self.limits.max_loss):,.2f} max)"
            )
            return verdict

        return verdict

    def loss_limit_would_breach(self, projected_pnl):
        """Proactive check: would this projected P&L breach the loss limit?"""
        buffer = getattr(config, "DAILY_LOSS_SAFETY_BUFFER", 0.90)
        return projected_pnl <= -abs(self.limits.max_loss) * buffer

    def remaining_loss_budget(self):
        """Dollars of loss still permitted today before the limit halts us."""
        buffer = getattr(config, "DAILY_LOSS_SAFETY_BUFFER", 0.90)
        return abs(self.limits.max_loss) * buffer + self.current_pnl

    def should_continue_trading(self):
        return self.active

    def summary(self):
        return {
            "active": self.active,
            "daily_pnl": round(self.current_pnl, 2),
            "max_profit": self.limits.max_profit,
            "max_loss": self.limits.max_loss,
            "per_trade_stop": self.limits.per_trade_stop_loss,
            "trades_today": self.trades_today,
            "open_positions": len(self.positions),
            "shutdown_reason": self.shutdown_reason,
            "profit_progress": round(
                max(0.0, self.current_pnl) / self.limits.max_profit * 100.0, 1
            ),
            "loss_progress": round(
                max(0.0, -self.current_pnl) / self.limits.max_loss * 100.0, 1
            ),
        }
