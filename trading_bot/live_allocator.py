"""Live auto-executing trend allocator.

Runs the VALIDATED trend-following strategy hands-off on a weekly cadence:
every ``rebalance_every`` bars it recomputes inverse-volatility target weights
for assets in a confirmed uptrend (with the SPY crash filter), then rebalances a
paper portfolio toward those weights. This is the "set-it-and-forget-it" engine
for the edge that actually beat the market out-of-sample.

Design notes
------------
* It keeps its OWN Portfolio + price history so it is fully independent of the
  tick-style intraday bot. Both can run; this one is the long-horizon edge.
* It is driven by daily bars (from CSV history at startup, then advanced one
  bar per ``step`` call). In a real deployment ``step`` would be called once per
  trading day by a scheduler; here the API loop advances it on a fast cadence
  for demonstration, controlled by ``bars_per_real_day`` only conceptually.
* Every rebalance and every regime flip raises a notification so you stay in
  the loop. The crash filter moving to RISK-OFF flattens to cash and alerts.
"""

import time

from trading_bot import config
from trading_bot.engine.portfolio import Portfolio
from trading_bot.trend_allocator import TrendAllocator


class LiveAllocator:
    def __init__(self, series_by_symbol, allocator=None, notifier=None,
                 logger=print, initial=None, costs_bps=2.0):
        self.series = series_by_symbol
        self.symbols = list(series_by_symbol.keys())
        self.N = min(len(v) for v in series_by_symbol.values()) if series_by_symbol else 0
        self.allocator = allocator or TrendAllocator(
            trend_window=config.ALLOCATOR_TREND_WINDOW,
            vol_window=config.ALLOCATOR_VOL_WINDOW,
            rebalance_every=config.ALLOCATOR_REBALANCE_EVERY,
            crash_filter=config.ALLOCATOR_CRASH_FILTER,
            market_symbol=config.ALLOCATOR_MARKET,
            max_weight=config.ALLOCATOR_MAX_WEIGHT,
        )
        self.notifier = notifier
        self.logger = logger
        self.costs_bps = costs_bps
        self.initial = initial if initial is not None else config.INITIAL_BALANCE
        self.portfolio = Portfolio(balance=self.initial)

        self.enabled = False
        self.cursor = self.allocator.warmup()   # current bar index
        self.last_rebalance_bar = None
        self.rebalances = 0
        self.total_costs = 0.0
        self.last_regime = None
        self.last_weights = {}
        self.history = []      # equity snapshots: [{bar, equity, regime}]

    # ------------------------------------------------------------------ #
    def _alert(self, title, message, level="INFO"):
        if self.notifier:
            self.notifier.notify(title, message, level=level)
        else:
            self.logger(f"[{level}] {title} — {message}")

    def _prices_at(self, idx):
        return {s: self.series[s][idx] for s in self.symbols}

    def equity_at(self, idx):
        return self.portfolio.equity(self._prices_at(idx))

    # ------------------------------------------------------------------ #
    def enable(self):
        if self.N < self.allocator.warmup() + 5:
            return False, "Not enough history to run the allocator."
        self.enabled = True
        self._alert(
            "📈 Auto-Allocator ENABLED",
            f"The validated trend strategy is now running hands-off on "
            f"{len(self.symbols)} assets. It rebalances every "
            f"{self.allocator.rebalance_every} bars (≈weekly) and moves to cash "
            f"when the market is in a downtrend.",
            level="SUCCESS")
        # Do an immediate first rebalance so we're invested right away.
        self.rebalance(self.cursor, force=True)
        return True, "Auto-allocator enabled."

    def disable(self):
        self.enabled = False
        self._alert("⏸️ Auto-Allocator disabled",
                    "The trend strategy is paused. Existing holdings are kept "
                    "until you re-enable or flatten.", level="INFO")

    def flatten(self, idx=None):
        idx = self.cursor if idx is None else idx
        prices = self._prices_at(idx)
        n = 0
        for symbol in list(self.portfolio.open_positions().keys()):
            pos = self.portfolio.get_position(symbol)
            if pos["size"] > 0:
                self.portfolio.execute_sell(symbol, prices[symbol], pos["size"])
                n += 1
        return n

    # ------------------------------------------------------------------ #
    def rebalance(self, idx, force=False):
        """Rebalance the portfolio toward target weights at bar ``idx``."""
        market_series = self.series.get(self.allocator.market_symbol)
        risk_on = self.allocator.market_ok(market_series, idx)
        weights = self.allocator.target_weights(self.series, idx, market_series)
        prices = self._prices_at(idx)
        equity = self.portfolio.equity(prices)

        # Detect & announce regime flips.
        regime = "RISK-ON" if risk_on else "RISK-OFF"
        if regime != self.last_regime:
            if regime == "RISK-OFF":
                self._alert(
                    "🛡️ Market downtrend — moving to CASH",
                    "The broad market fell below its long-term trend. The "
                    "allocator is going defensive (cash) to protect capital "
                    "until the uptrend resumes.",
                    level="WARNING")
            elif self.last_regime is not None:
                self._alert(
                    "🟢 Uptrend resumed — re-investing",
                    "The market is back above its long-term trend. The "
                    "allocator is redeploying into leading assets.",
                    level="SUCCESS")
            self.last_regime = regime

        # Rebalance: sell what's no longer targeted, then buy/scale targets.
        # 1) Liquidate positions not in the new target set.
        for symbol in list(self.portfolio.open_positions().keys()):
            if symbol not in weights:
                pos = self.portfolio.get_position(symbol)
                if pos["size"] > 0:
                    self.portfolio.execute_sell(symbol, prices[symbol], pos["size"])

        # 2) Move each targeted holding toward its target dollar value.
        for symbol, w in weights.items():
            price = prices[symbol]
            target_val = equity * w
            pos = self.portfolio.get_position(symbol)
            cur_val = pos["size"] * price
            diff = target_val - cur_val
            if abs(diff) < equity * 0.005:   # ignore tiny drifts (<0.5% equity)
                continue
            units = abs(diff) / price
            cost = abs(diff) * self.costs_bps / 1e4
            self.total_costs += cost
            self.portfolio.balance -= cost
            if diff > 0:
                self.portfolio.execute_buy(symbol, price, units)
            else:
                sell_units = min(units, pos["size"])
                if sell_units > 0:
                    self.portfolio.execute_sell(symbol, price, sell_units)

        self.last_rebalance_bar = idx
        self.rebalances += 1
        self.last_weights = {s: round(w, 4) for s, w in weights.items()}

        holdings = ", ".join(f"{s} {w*100:.0f}%" for s, w in
                             sorted(weights.items(), key=lambda kv: -kv[1])[:5])
        self._alert(
            "🔄 Auto-rebalance executed",
            (f"Rebalanced to {len(weights)} holdings ({regime}). "
             f"Top: {holdings or 'CASH'}. "
             f"Equity ${self.portfolio.equity(prices):,.2f}."),
            level="INFO")
        return {"risk_on": risk_on, "weights": self.last_weights}

    # ------------------------------------------------------------------ #
    def step(self):
        """Advance one bar; rebalance if the cadence is due. Called by the loop."""
        if not self.enabled:
            return
        if self.cursor >= self.N - 1:
            return  # reached end of available history
        self.cursor += 1
        idx = self.cursor
        equity = self.equity_at(idx)
        self.history.append({"bar": idx, "equity": round(equity, 2),
                             "regime": self.last_regime})
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
        if self.allocator.should_rebalance(idx):
            self.rebalance(idx)

    # ------------------------------------------------------------------ #
    def status(self):
        idx = self.cursor
        prices = self._prices_at(idx) if self.symbols else {}
        equity = self.portfolio.equity(prices) if self.symbols else self.initial
        positions = []
        for symbol, pos in self.portfolio.open_positions().items():
            price = prices.get(symbol, pos["avg_price"])
            positions.append({
                "symbol": symbol,
                "weight": round(pos["size"] * price / equity, 4) if equity else 0,
                "value": round(pos["size"] * price, 2),
                "unrealised": round((price - pos["avg_price"]) * pos["size"], 2),
            })
        positions.sort(key=lambda p: -p["value"])
        invested = sum(p["value"] for p in positions)
        return {
            "enabled": self.enabled,
            "regime": self.last_regime or "—",
            "equity": round(equity, 2),
            "return_pct": round((equity / self.initial - 1) * 100, 2),
            "cash": round(self.portfolio.balance, 2),
            "cash_pct": round(max(0.0, 1 - invested / equity) * 100, 1) if equity else 100.0,
            "positions": positions,
            "rebalances": self.rebalances,
            "total_costs": round(self.total_costs, 2),
            "bar": idx,
            "bars_total": self.N,
            "last_weights": self.last_weights,
        }
