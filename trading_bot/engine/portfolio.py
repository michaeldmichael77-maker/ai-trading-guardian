"""Portfolio accounting: cash, positions, realised/unrealised P&L and stats."""

import time


class Portfolio:
    def __init__(self, balance=100_000.0):
        self.starting_balance = balance
        self.balance = balance            # cash + realised P&L
        self.daily_start_balance = balance
        self.daily_pnl = 0.0

        # symbol -> {size, avg_price, side, entry_time}
        self.positions = {}

        # Trade log of *closed* trades for performance stats.
        self.closed_trades = []

        # Running performance metrics.
        self.peak_equity = balance
        self.max_drawdown = 0.0

    # ------------------------------------------------------------------ #
    # Position helpers
    # ------------------------------------------------------------------ #
    def get_position(self, symbol):
        return self.positions.get(
            symbol, {"size": 0, "avg_price": 0.0, "side": None, "entry_time": None}
        )

    def open_positions(self):
        return {s: p for s, p in self.positions.items() if p["size"] != 0}

    def position_count(self):
        return len(self.open_positions())

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #
    def execute_buy(self, symbol, price, size):
        cost = price * size
        self.balance -= cost
        pos = self.get_position(symbol)
        if pos["size"] == 0:
            self.positions[symbol] = {
                "size": size,
                "avg_price": price,
                "side": "LONG",
                "entry_time": time.time(),
            }
        else:
            total = pos["size"] + size
            new_avg = (pos["avg_price"] * pos["size"] + price * size) / total
            self.positions[symbol] = {
                "size": total,
                "avg_price": new_avg,
                "side": "LONG",
                "entry_time": pos["entry_time"],
            }
        return {"symbol": symbol, "action": "BUY", "price": price, "size": size}

    def execute_short(self, symbol, price, size):
        """Open or add to a SHORT position (stored as negative size).

        We receive proceeds up front; the obligation to buy back is captured by
        the negative size, so the existing equity()/unrealised_pnl() formulas
        value the short correctly with no special-casing.
        """
        if size <= 0:
            return None
        self.balance += price * size
        pos = self.get_position(symbol)
        if pos["size"] == 0:
            self.positions[symbol] = {
                "size": -size,
                "avg_price": price,
                "side": "SHORT",
                "entry_time": time.time(),
            }
        elif pos["size"] < 0:
            cur = abs(pos["size"])
            total = cur + size
            new_avg = (pos["avg_price"] * cur + price * size) / total
            self.positions[symbol] = {
                "size": -total,
                "avg_price": new_avg,
                "side": "SHORT",
                "entry_time": pos["entry_time"],
            }
        else:
            # Refuse to short while long (caller should flatten first).
            return None
        return {"symbol": symbol, "action": "SHORT", "price": price, "size": size}

    def execute_cover(self, symbol, price, size):
        """Buy back (cover) all/part of a SHORT position."""
        pos = self.get_position(symbol)
        if pos["size"] >= 0:
            return None
        cur = abs(pos["size"])
        size = min(size, cur)
        self.balance -= price * size

        realised = (pos["avg_price"] - price) * size   # short profits when price falls
        self.daily_pnl += realised
        self._record_close(symbol, pos["avg_price"], price, size, realised)

        remaining = cur - size
        if remaining <= 0:
            self.positions.pop(symbol, None)
        else:
            pos["size"] = -remaining
            self.positions[symbol] = pos
        return {
            "symbol": symbol,
            "action": "COVER",
            "price": price,
            "size": size,
            "pnl": realised,
        }

    def execute_sell(self, symbol, price, size):
        pos = self.get_position(symbol)
        if pos["size"] <= 0:
            return None
        size = min(size, pos["size"])
        proceeds = price * size
        self.balance += proceeds

        realised = (price - pos["avg_price"]) * size
        self.daily_pnl += realised
        self._record_close(symbol, pos["avg_price"], price, size, realised)

        remaining = pos["size"] - size
        if remaining <= 0:
            self.positions.pop(symbol, None)
        else:
            pos["size"] = remaining
            self.positions[symbol] = pos
        return {
            "symbol": symbol,
            "action": "SELL",
            "price": price,
            "size": size,
            "pnl": realised,
        }

    def _record_close(self, symbol, entry, exit_price, size, pnl):
        self.closed_trades.append(
            {
                "symbol": symbol,
                "entry": entry,
                "exit": exit_price,
                "size": size,
                "pnl": pnl,
                "time": time.time(),
            }
        )

    # ------------------------------------------------------------------ #
    # Valuation & metrics
    # ------------------------------------------------------------------ #
    def unrealised_pnl(self, price_map):
        total = 0.0
        for symbol, pos in self.open_positions().items():
            price = price_map.get(symbol, pos["avg_price"])
            total += (price - pos["avg_price"]) * pos["size"]
        return total

    def equity(self, price_map):
        """Cash already includes realised P&L; add mark-to-market positions."""
        market_value = 0.0
        for symbol, pos in self.open_positions().items():
            price = price_map.get(symbol, pos["avg_price"])
            market_value += price * pos["size"]
        return self.balance + market_value

    def gross_exposure(self, price_map):
        """Sum of absolute notional across all open positions (long + short).

        Used for buying-power / leverage checks: a basket of shorts adds to
        exposure even though it credits cash, so we measure |size| * price.
        """
        total = 0.0
        for symbol, pos in self.open_positions().items():
            price = price_map.get(symbol, pos["avg_price"])
            total += abs(pos["size"]) * price
        return total

    def update_equity_curve(self, price_map):
        eq = self.equity(price_map)
        if eq > self.peak_equity:
            self.peak_equity = eq
        dd = self.peak_equity - eq
        if dd > self.max_drawdown:
            self.max_drawdown = dd
        return eq

    def reset_daily(self):
        self.daily_start_balance = self.balance
        self.daily_pnl = 0.0

    # ------------------------------------------------------------------ #
    # Stats for the UI
    # ------------------------------------------------------------------ #
    def stats(self):
        wins = [t for t in self.closed_trades if t["pnl"] > 0]
        losses = [t for t in self.closed_trades if t["pnl"] <= 0]
        total = len(self.closed_trades)
        gross_profit = sum(t["pnl"] for t in wins)
        gross_loss = abs(sum(t["pnl"] for t in losses))

        win_rate = (len(wins) / total * 100.0) if total else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (
            gross_profit if gross_profit > 0 else 0.0
        )
        avg_win = (gross_profit / len(wins)) if wins else 0.0
        avg_loss = (gross_loss / len(losses)) if losses else 0.0

        return {
            "total_trades": total,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "max_drawdown": round(self.max_drawdown, 2),
        }
