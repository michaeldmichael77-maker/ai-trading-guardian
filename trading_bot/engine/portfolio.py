from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class TradeRecord:
    symbol: str
    entry_price: float
    exit_price: float
    pnl: float
    timestamp: str
    reason: str

@dataclass
class Portfolio:
    balance: float
    position_size: float = 0.0
    entry_price: float = 0.0
    daily_pnl: float = 0.0
    peak_price_during_trade: float = 0.0
    trade_history: list = None

    def __post_init__(self):
        if self.trade_history is None:
            self.trade_history = []

    def update_pnl(self, current_price: float):
        if self.position_size > 0:
            unrealized_pnl = (current_price - self.entry_price) * self.position_size
            if current_price > self.peak_price_during_trade:
                self.peak_price_during_trade = current_price
            return unrealized_pnl
        return 0.0

    def execute_buy(self, price: float, amount: float):
        cost = price * amount
        if self.balance >= cost:
            self.balance -= cost
            self.position_size += amount
            self.entry_price = price
            self.peak_price_during_trade = price
            return True
        return False

    def execute_sell(self, price: float, reason: str = "AI Signal"):
        if self.position_size > 0:
            revenue = price * self.position_size
            self.balance += revenue
            trade_pnl = (price - self.entry_price) * self.position_size
            self.daily_pnl += trade_pnl
            record = TradeRecord(
                symbol="BTC/USD",
                entry_price=self.entry_price,
                exit_price=price,
                pnl=trade_pnl,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                reason=reason
            )
            self.trade_history.append(record)
            self.position_size = 0.0
            self.entry_price = 0.0
            self.peak_price_during_trade = 0.0
            return trade_pnl
        return 0.0