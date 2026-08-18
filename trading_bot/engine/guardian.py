from trading_bot import config

class Guardian:
    """The 'Security Guard' that enforces risk management rules."""
    def __init__(self, portfolio):
        self.portfolio = portfolio
        self.is_system_active = True
        self.reason_for_shutdown = ""

    def check_risk_limits(self, current_price: float):
        if not self.is_system_active:
            return "STOPPED"

        if self.portfolio.daily_pnl <= -config.DAILY_LOSS_LIMIT:
            self.is_system_active = False
            self.reason_for_shutdown = f"Daily Loss Limit reached (${config.DAILY_LOSS_LIMIT})"
            return "KILL_SWITCH"

        if self.portfolio.daily_pnl >= config.DAILY_PROFIT_LIMIT:
            self.is_system_active = False
            self.reason_for_shutdown = f"Daily Profit Limit reached (${config.DAILY_PROFIT_LIMIT})"
            return "KILL_SWITCH"

        if self.portfolio.position_size > 0:
            drop_from_peak = self.portfolio.peak_price_during_trade - current_price
            if drop_from_peak >= config.TRAILING_STOP_DISTANCE:
                return "TRAILING_STOP_TRIGGERED"

        return "OK"

    def restart_system(self):
        self.is_system_active = True
        self.reason_for_shutdown = ""
        print("System restarted by user.")