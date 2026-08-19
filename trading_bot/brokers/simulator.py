"""Simulator broker adapter.

Wraps the existing in-process MarketSimulator + Portfolio behind the same
BrokerAdapter interface used for Alpaca, so the rest of the system can treat
"the simulator" and "a real broker" identically. This is what the app uses by
default (safe, free, no account, fake money & simulated prices).
"""

from trading_bot.brokers.base import BrokerAdapter


class SimulatorAdapter(BrokerAdapter):
    name = "Simulator"
    is_live = False

    def __init__(self, market, portfolio, last_prices, logger=print):
        self.market = market
        self.portfolio = portfolio
        self.last_prices = last_prices      # shared dict of current prices
        self.logger = logger
        self.connected = True               # always available

    def connect(self):
        self.connected = True
        return {"connected": True, "name": self.name, "is_live": False,
                "status": "SIMULATED"}

    def get_account(self):
        equity = self.portfolio.equity(self.last_prices)
        return {
            "cash": round(self.portfolio.balance, 2),
            "equity": round(equity, 2),
            "buying_power": round(self.portfolio.balance, 2),
            "currency": "USD",
            "status": "SIMULATED",
            "account_number": "PAPER-SIM",
        }

    def get_positions(self):
        out = []
        for symbol, pos in self.portfolio.open_positions().items():
            price = self.last_prices.get(symbol, pos["avg_price"])
            out.append({
                "symbol": symbol,
                "qty": abs(pos["size"]),
                "avg_price": pos["avg_price"],
                "side": pos["side"],
                "market_value": round(pos["size"] * price, 2),
                "unrealised_pnl": round((price - pos["avg_price"]) * pos["size"], 2),
            })
        return out

    def get_price(self, symbol):
        return self.last_prices.get(symbol)

    def submit_order(self, symbol, qty, side, order_type="market",
                     time_in_force="day"):
        price = self.last_prices.get(symbol)
        if price is None:
            return {"status": "rejected", "reason": "no price"}
        if side == "buy":
            self.portfolio.execute_buy(symbol, price, qty)
        else:
            pos = self.portfolio.get_position(symbol)
            sell_qty = min(qty, pos["size"]) if pos["size"] > 0 else qty
            self.portfolio.execute_sell(symbol, price, sell_qty)
        return {"id": "sim", "symbol": symbol, "qty": qty, "side": side,
                "status": "filled"}

    def close_position(self, symbol):
        pos = self.portfolio.get_position(symbol)
        if pos["size"] > 0:
            self.portfolio.execute_sell(symbol, self.last_prices.get(symbol, pos["avg_price"]),
                                        pos["size"])
            return {"status": "filled"}
        return None

    def close_all_positions(self):
        n = 0
        for symbol in list(self.portfolio.open_positions().keys()):
            if self.close_position(symbol):
                n += 1
        return n
