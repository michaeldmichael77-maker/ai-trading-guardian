"""Backtest harness for the TrendAllocator on real (CSV) data.

Separate from the tick-style Backtester because the allocator operates on a
portfolio-rebalance model (target weights) rather than discrete entry/exit
signals. Reports the same metric vocabulary so results are comparable, and
includes a buy-and-hold benchmark plus walk-forward train/test split.

CLI:
    PYTHONPATH=. python3 -m trading_bot.allocator_backtest --csv-dir data_real_long
    PYTHONPATH=. python3 -m trading_bot.allocator_backtest --csv-dir data_real_long --walk-forward
"""

import argparse
import math
import os
import statistics

from trading_bot import config
from trading_bot.engine.csv_market import CSVMarket
from trading_bot.trend_allocator import TrendAllocator


def _metrics(equity_curve):
    if len(equity_curve) < 3:
        return {"return_pct": 0.0, "sharpe": 0.0, "max_drawdown_pct": 0.0}
    rets = [equity_curve[i] / equity_curve[i - 1] - 1.0
            for i in range(1, len(equity_curve)) if equity_curve[i - 1]]
    mean = statistics.mean(rets) if rets else 0.0
    sd = statistics.pstdev(rets) if rets else 0.0
    sharpe = (mean / sd * math.sqrt(252)) if sd else 0.0
    peak, mdd = -1e18, 0.0
    for e in equity_curve:
        peak = max(peak, e)
        if peak > 0:
            mdd = max(mdd, (peak - e) / peak)
    return {
        "return_pct": round((equity_curve[-1] / equity_curve[0] - 1.0) * 100, 2),
        "sharpe": round(sharpe, 3),
        "max_drawdown_pct": round(mdd * 100, 2),
        "final_equity": round(equity_curve[-1], 2),
    }


class AllocatorBacktest:
    def __init__(self, data_dir, allocator=None, costs_bps=2.0,
                 initial=config.INITIAL_BALANCE):
        market = CSVMarket(data_dir)
        self.symbols = market.symbols
        # Build full close series per symbol, trimmed to common length.
        self.series = {s: list(market.series[s]) for s in self.symbols}
        n = min(len(v) for v in self.series.values())
        self.series = {s: v[-n:] for s, v in self.series.items()}
        self.N = n
        self.allocator = allocator or TrendAllocator()
        self.costs_bps = costs_bps
        self.initial = initial
        self.rebalances = 0

    def _market_series(self):
        return self.series.get(self.allocator.market_symbol)

    def run(self, start=None, end=None):
        start = self.allocator.warmup() if start is None else start
        end = self.N if end is None else end
        cash = self.initial
        shares = {s: 0.0 for s in self.symbols}
        equity_curve = []
        market_series = self._market_series()

        for i in range(start, end):
            equity = cash + sum(shares[s] * self.series[s][i] for s in self.symbols)
            equity_curve.append(equity)
            if not self.allocator.should_rebalance(i):
                continue

            weights = self.allocator.target_weights(self.series, i, market_series)
            self.rebalances += 1
            for s in self.symbols:
                price = self.series[s][i]
                target_val = equity * weights.get(s, 0.0)
                cur_val = shares[s] * price
                diff = target_val - cur_val
                cost = abs(diff) * self.costs_bps / 1e4
                cash -= diff + cost
                shares[s] += diff / price

        m = _metrics(equity_curve)
        m["rebalances"] = self.rebalances
        m["bars"] = len(equity_curve)
        return m

    def benchmark_buy_hold(self, symbol="SPY", start=None, end=None):
        start = self.allocator.warmup() if start is None else start
        end = self.N if end is None else end
        if symbol not in self.series:
            return None
        s = self.series[symbol]
        curve = s[start:end]
        return _metrics(curve)


def main():
    ap = argparse.ArgumentParser(description="TrendAllocator backtest")
    ap.add_argument("--csv-dir", default="data_real_long")
    ap.add_argument("--walk-forward", action="store_true")
    ap.add_argument("--trend", type=int, default=200)
    ap.add_argument("--vol", type=int, default=40)
    ap.add_argument("--rebalance", type=int, default=5)
    ap.add_argument("--no-crash-filter", action="store_true")
    args = ap.parse_args()

    alloc = TrendAllocator(trend_window=args.trend, vol_window=args.vol,
                           rebalance_every=args.rebalance,
                           crash_filter=not args.no_crash_filter)
    bt = AllocatorBacktest(args.csv_dir, allocator=alloc)

    print("=" * 60)
    print(f" TREND ALLOCATOR  ({len(bt.symbols)} symbols, {bt.N} bars"
          f" ~ {bt.N/252:.1f}y)")
    print(f" config: trend={args.trend} vol={args.vol} rebal={args.rebalance}"
          f" crash_filter={not args.no_crash_filter}")
    print("=" * 60)

    if args.walk_forward:
        split = int(bt.N * 0.6)
        tr = bt.run(end=split)
        te = bt.run(start=split)
        bh = bt.benchmark_buy_hold("SPY", start=split)
        print(f"  TRAIN  (first 60%): ret {tr['return_pct']:>8.1f}%  "
              f"sharpe {tr['sharpe']:>5.2f}  maxDD {tr['max_drawdown_pct']:>5.1f}%")
        print(f"  TEST   (last  40%): ret {te['return_pct']:>8.1f}%  "
              f"sharpe {te['sharpe']:>5.2f}  maxDD {te['max_drawdown_pct']:>5.1f}%")
        if bh:
            print(f"  TEST Buy&Hold SPY : ret {bh['return_pct']:>8.1f}%  "
                  f"maxDD {bh['max_drawdown_pct']:>5.1f}%")
        if bh:
            ret_ratio = te["return_pct"] / bh["return_pct"] if bh["return_pct"] else 0
            dd_better = te["max_drawdown_pct"] < bh["max_drawdown_pct"]
            if te["return_pct"] >= bh["return_pct"] and dd_better:
                verdict = "BEATS benchmark OOS on BOTH return and risk"
            elif ret_ratio >= 0.9 and dd_better:
                verdict = ("MATCHES benchmark return with LOWER drawdown "
                           f"({te['max_drawdown_pct']}% vs {bh['max_drawdown_pct']}%) "
                           "-> better risk-adjusted")
            elif dd_better:
                verdict = ("lower return but much safer "
                           f"(DD {te['max_drawdown_pct']}% vs {bh['max_drawdown_pct']}%)")
            else:
                verdict = "does not improve on benchmark OOS"
            print(f"\n  Verdict: {verdict}")
    else:
        r = bt.run()
        bh = bt.benchmark_buy_hold("SPY")
        print(f"  Strategy : ret {r['return_pct']:>8.1f}%  sharpe {r['sharpe']:>5.2f}"
              f"  maxDD {r['max_drawdown_pct']:>5.1f}%  rebalances {r['rebalances']}")
        if bh:
            print(f"  Buy&Hold : ret {bh['return_pct']:>8.1f}%"
                  f"  maxDD {bh['max_drawdown_pct']:>5.1f}%")


if __name__ == "__main__":
    main()
