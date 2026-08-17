"""Deterministic backtest harness.

Replays a seeded price series through the full Hive-Mind + risk stack (without
the FastAPI loop) so strategy changes can be compared objectively. Because the
MarketSimulator is seedable, results are reproducible.

Run:
    PYTHONPATH=. python3 -m trading_bot.backtest
    PYTHONPATH=. python3 -m trading_bot.backtest --ticks 1500 --seed 7
"""

import argparse
import math

from trading_bot import config
from trading_bot.engine.market import MarketSimulator
from trading_bot.engine.portfolio import Portfolio
from trading_bot.regime_detector import RegimeDetector
from trading_bot.multi_timeframe import MultiTimeframeConfirmation
from trading_bot.correlation_heat import PortfolioHeatMonitor
from trading_bot.drawdown_recovery import DrawdownRecovery
from trading_bot.sentiment_overlay import SentimentOverlay
from trading_bot.hive_mind import HiveMind
from trading_bot.execution_quality import ExecutionQualityTracker
from trading_bot.exit_manager import ExitManager


class Backtester:
    def __init__(self, seed=42, symbols=None, market=None):
        # ``market`` lets callers inject a CSVMarket (real data) in place of the
        # default synthetic simulator. When a market is supplied we adopt its
        # symbol list so the two stay in sync.
        if market is not None:
            self.market = market
            self.symbols = symbols or getattr(market, "symbols", None) \
                or config.SYMBOLS
        else:
            self.symbols = symbols or config.SYMBOLS
            self.market = MarketSimulator(seed=seed)
        self.portfolio = Portfolio(balance=config.INITIAL_BALANCE)
        self.regime = RegimeDetector()
        self.mtf = MultiTimeframeConfirmation()
        self.heat = PortfolioHeatMonitor()
        self.dd = DrawdownRecovery()
        self.sentiment = SentimentOverlay(self.symbols, seed=seed)
        self.hive = HiveMind()
        # Same realistic fill model as the live path, seeded for reproducibility.
        self.exec_quality = ExecutionQualityTracker(seed=seed)
        self.exits = ExitManager()
        self.buffers = {s: [] for s in self.symbols}
        self.equity_curve = []
        self.entries = {}
        self.total_costs = 0.0   # cumulative commissions paid (for reconciliation)

    def _size_and_risk(self, symbol, price, conf, risk_mult):
        """Return (units, per_unit_stop_distance, risk_dollars).

        Volatility-based sizing: risk a fixed small % of equity per trade with
        the stop placed STOP_ATR_MULT volatility-units away. This adapts to bar
        granularity so a daily-bar position is ~20x smaller than a tick-bar one
        for the same dollar risk -- the core fix for the giant real-data losses.
        """
        equity = self.portfolio.equity(self._prices())
        if config.USE_VOL_SIZING:
            from trading_bot.volatility import expected_move
            move = expected_move(self.buffers[symbol], price,
                                 window=config.VOL_WINDOW)
            stop_distance = max(move * config.STOP_ATR_MULT, 1e-9)
            risk_dollars = equity * config.RISK_PER_TRADE_PCT * conf * risk_mult
            units = risk_dollars / stop_distance
        else:
            vol = config.SYMBOL_VOL.get(symbol, 0.0015)
            stop_distance = max(price * vol * 3.0, 0.01)
            risk_dollars = config.PER_TRADE_STOP_LOSS * conf * risk_mult
            units = risk_dollars / stop_distance

        # Cap any single position's notional at MAX_POSITION_PCT of equity.
        max_notional = equity * config.MAX_POSITION_PCT
        if units * price > max_notional:
            units = max_notional / price

        # Tail-risk cap: bound the loss from a worst-plausible overnight GAP
        # (markets can't be stopped out while closed). Size so a 25% adverse
        # gap costs at most MAX_SINGLE_LOSS_PCT of equity.
        gap_cap = getattr(config, "MAX_SINGLE_LOSS_PCT", None)
        if gap_cap:
            assumed_gap = 0.25  # worst-case single-bar adverse move
            max_units_for_gap = (equity * gap_cap) / (price * assumed_gap)
            units = min(units, max_units_for_gap)

        units = max(0.0, round(units, 6))
        # Effective dollar risk after the notional cap.
        eff_risk = units * stop_distance
        return units, stop_distance, eff_risk

    def _size(self, symbol, price, conf, risk_mult):
        units, _, _ = self._size_and_risk(symbol, price, conf, risk_mult)
        return units

    def _prices(self):
        return self.market.snapshot()

    def run(self, ticks=1000):
        for _ in range(ticks):
            prices = {}
            for symbol in self.symbols:
                price = self.market.get_price(symbol)
                prices[symbol] = price
                self.buffers[symbol].append(price)
                if len(self.buffers[symbol]) > 200:
                    self.buffers[symbol].pop(0)
                self.sentiment.update(symbol)
                self._step_symbol(symbol, price)

            equity = self.portfolio.update_equity_curve(prices)
            self.equity_curve.append(equity)
            self.dd.update(equity, self.portfolio.peak_equity)
            self.heat.compute(self.portfolio.open_positions(), equity,
                              config.PER_TRADE_STOP_LOSS)
        return self.report()

    def _step_symbol(self, symbol, price):
        buf = self.buffers[symbol]
        if len(buf) < config.WARMUP_TICKS:
            return
        regime = self.regime.detect_regime(buf)
        mtf = self.mtf.check_alignment(buf)
        senti = self.sentiment.get(symbol)
        decision = self.hive.decide(buf, regime=regime, mtf=mtf, sentiment=senti)

        pos = self.portfolio.get_position(symbol)
        # Managed exits: hard stop / take-profit / trailing stop (both sides).
        if pos["size"] != 0:
            verdict = self.exits.check(symbol, pos, price)
            if verdict:
                self._flatten(symbol, pos, price)
                return

        signal, conf = decision["signal"], decision["confidence"]
        # Opposite-signal exit.
        if signal == "SELL" and pos["size"] > 0:
            self._flatten(symbol, pos, price)
            return
        if signal == "BUY" and pos["size"] < 0:
            self._flatten(symbol, pos, price)
            return

        min_conf = config.MIN_CONFIDENCE + self.dd.confidence_bonus
        if signal in ("BUY", "SELL") and pos["size"] == 0 and conf >= min_conf:
            if not mtf["aligned"]:
                return
            equity = self.portfolio.equity(self._prices())
            allowed, _ = self.heat.can_add_position(
                self.portfolio.open_positions(), equity,
                config.PER_TRADE_STOP_LOSS, symbol)
            if not allowed:
                return
            size, stop_dist, risk_dollars = self._size_and_risk(
                symbol, price, conf, self.dd.risk_multiplier)
            if size <= 0:
                return
            # Buying-power / gross-leverage cap (longs and shorts alike).
            projected_gross = (self.portfolio.gross_exposure(self._prices())
                               + abs(size) * price)
            if equity <= 0 or projected_gross > equity * config.MAX_GROSS_LEVERAGE:
                return
            if signal == "BUY":
                fill = self.exec_quality.record_fill(symbol, price, "BUY")
                self.portfolio.execute_buy(symbol, fill["fill"], size)
            else:
                fill = self.exec_quality.record_fill(symbol, price, "SELL")
                self.portfolio.execute_short(symbol, fill["fill"], size)
            self._charge_costs(size, fill["fill"])
            # Hand the volatility-based dollar stop for THIS position to exits.
            self.exits.on_open(symbol, risk_dollars=risk_dollars)

    def _charge_costs(self, units, fill_price):
        """Deduct commission for one fill from portfolio cash."""
        notional = abs(units) * fill_price
        cost = config.COMMISSION_PER_TRADE + notional * (config.COMMISSION_BPS / 1e4)
        if cost:
            self.portfolio.balance -= cost
            self.total_costs += cost

    def _flatten(self, symbol, pos, price):
        """Close an open position (long -> sell, short -> cover)."""
        if pos["size"] > 0:
            fill = self.exec_quality.record_fill(symbol, price, "SELL")
            self.portfolio.execute_sell(symbol, fill["fill"], pos["size"])
            self._charge_costs(pos["size"], fill["fill"])
        elif pos["size"] < 0:
            fill = self.exec_quality.record_fill(symbol, price, "BUY")
            self.portfolio.execute_cover(symbol, fill["fill"], abs(pos["size"]))
            self._charge_costs(pos["size"], fill["fill"])
        self.exits.on_close(symbol)

    def report(self):
        stats = self.portfolio.stats()
        final_equity = self.equity_curve[-1] if self.equity_curve else config.INITIAL_BALANCE
        total_return = final_equity - config.INITIAL_BALANCE
        return_pct = total_return / config.INITIAL_BALANCE * 100.0
        sharpe = self._sharpe()
        return {
            "final_equity": round(final_equity, 2),
            "total_return": round(total_return, 2),
            "return_pct": round(return_pct, 3),
            "sharpe": round(sharpe, 3),
            "max_drawdown": stats["max_drawdown"],
            "max_drawdown_pct": round(
                stats["max_drawdown"] / config.INITIAL_BALANCE * 100, 3),
            **stats,
        }

    def _sharpe(self):
        if len(self.equity_curve) < 3:
            return 0.0
        rets = []
        for i in range(1, len(self.equity_curve)):
            prev = self.equity_curve[i - 1]
            if prev:
                rets.append((self.equity_curve[i] - prev) / prev)
        if len(rets) < 2:
            return 0.0
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        sd = math.sqrt(var)
        if sd == 0:
            return 0.0
        # Annualise loosely (per-tick -> sqrt scaling); illustrative only.
        return (mean / sd) * math.sqrt(len(rets))


def main():
    ap = argparse.ArgumentParser(description="AI Trading Guardian backtester")
    ap.add_argument("--ticks", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--csv-dir", type=str, default=None,
                    help="Replay real data from a directory of <SYMBOL>.csv files")
    args = ap.parse_args()

    if args.csv_dir:
        from trading_bot.engine.csv_market import CSVMarket
        market = CSVMarket(args.csv_dir)
        bt = Backtester(market=market)
        # Replay every available bar (capped by the longest run we asked for).
        ticks = min(args.ticks, market.length()) if args.ticks else market.length()
        report = bt.run(ticks=ticks)
        source = f"CSV {args.csv_dir} ({len(market.symbols)} symbols)"
    else:
        bt = Backtester(seed=args.seed)
        ticks = args.ticks
        report = bt.run(ticks=ticks)
        source = f"simulator seed={args.seed}"

    print("=" * 52)
    print(f" BACKTEST REPORT  ({source}, ticks={ticks})")
    print("=" * 52)
    print(f"  Final equity      : ${report['final_equity']:,.2f}")
    print(f"  Total return      : ${report['total_return']:,.2f} "
          f"({report['return_pct']:+.2f}%)")
    print(f"  Sharpe (approx)   : {report['sharpe']}")
    print(f"  Max drawdown      : ${report['max_drawdown']:,.2f} "
          f"({report['max_drawdown_pct']:.2f}%)")
    print("-" * 52)
    print(f"  Total trades      : {report['total_trades']}")
    print(f"  Win rate          : {report['win_rate']}%")
    print(f"  Profit factor     : {report['profit_factor']}")
    print(f"  Avg win / loss    : ${report['avg_win']} / ${report['avg_loss']}")
    print("=" * 52)


if __name__ == "__main__":
    main()
