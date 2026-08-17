"""Offline strategy parameter sweep.

Uses the deterministic backtester to grid-search exit/entry parameters, scoring
each candidate by mean Sharpe across several seeds (robustness over luck). This
is the *offline* counterpart to the live AutoOptimizer: the live optimizer nudges
voter weights tick-by-tick, while this validates structural parameters before
they ship as config defaults.

Run:
    PYTHONPATH=. python3 -m trading_bot.optimize_sweep
    PYTHONPATH=. python3 -m trading_bot.optimize_sweep --ticks 800 --top 8
"""

import argparse
import itertools
import statistics

from trading_bot import config
from trading_bot.backtest import Backtester
from trading_bot.exit_manager import ExitManager


# Search space (kept small so a full sweep runs in seconds).
GRID = {
    "min_confidence": [0.55, 0.60, 0.65],
    "take_profit_r": [0.0, 3.0],          # 0 = let winners run
    "trail_activate_r": [1.0, 1.5],
    "trail_giveback": [0.4, 0.5],
}

SEEDS = [1, 7, 42, 99, 123, 256, 500]


def evaluate(params, ticks, seeds):
    """Return aggregate metrics for one parameter set across seeds."""
    rets, sharpes, wins, pfs, dds = [], [], [], [], []
    original_min_conf = config.MIN_CONFIDENCE
    try:
        config.MIN_CONFIDENCE = params["min_confidence"]
        for seed in seeds:
            bt = Backtester(seed=seed)
            bt.exits = ExitManager(
                take_profit_r=params["take_profit_r"],
                trail_activate_r=params["trail_activate_r"],
                trail_giveback=params["trail_giveback"],
            )
            r = bt.run(ticks=ticks)
            rets.append(r["return_pct"])
            sharpes.append(r["sharpe"])
            wins.append(r["win_rate"])
            pfs.append(r["profit_factor"])
            dds.append(r["max_drawdown_pct"])
    finally:
        config.MIN_CONFIDENCE = original_min_conf

    return {
        "mean_return": statistics.mean(rets),
        "mean_sharpe": statistics.mean(sharpes),
        "mean_win": statistics.mean(wins),
        "mean_pf": statistics.mean(pfs),
        "mean_dd": statistics.mean(dds),
        "worst_return": min(rets),
    }


def run_sweep(ticks=800, seeds=SEEDS, top=10):
    keys = list(GRID.keys())
    combos = [dict(zip(keys, vals)) for vals in itertools.product(*GRID.values())]
    results = []
    for params in combos:
        metrics = evaluate(params, ticks, seeds)
        results.append((params, metrics))
    # Rank by mean Sharpe, tie-break by worst-case return (robustness).
    results.sort(key=lambda x: (x[1]["mean_sharpe"], x[1]["worst_return"]),
                 reverse=True)
    return results[:top]


def walk_forward(ticks=800, train_seeds=None, test_seeds=None):
    """In-sample / out-of-sample validation.

    Pick the best parameter set on the *training* seeds, then re-score it on the
    *test* seeds it has never seen. A big drop from train to test is the
    signature of overfitting; comparable numbers mean the params generalise.

    Returns (best_params, train_metrics, test_metrics).
    """
    train_seeds = train_seeds or [1, 7, 42, 99]
    test_seeds = test_seeds or [123, 256, 500]

    keys = list(GRID.keys())
    combos = [dict(zip(keys, vals)) for vals in itertools.product(*GRID.values())]

    best = None  # (params, train_metrics)
    for params in combos:
        m = evaluate(params, ticks, train_seeds)
        score = (m["mean_sharpe"], m["worst_return"])
        if best is None or score > (best[1]["mean_sharpe"], best[1]["worst_return"]):
            best = (params, m)

    best_params, train_metrics = best
    test_metrics = evaluate(best_params, ticks, test_seeds)
    return best_params, train_metrics, test_metrics


def current_config_params():
    """The parameters currently shipping as config defaults."""
    return {
        "min_confidence": config.MIN_CONFIDENCE,
        "take_profit_r": config.TAKE_PROFIT_R,
        "trail_activate_r": config.TRAIL_ACTIVATE_R,
        "trail_giveback": config.TRAIL_GIVEBACK,
    }


def compare(ticks=800, seeds=SEEDS):
    """Compare the current shipping config against the best grid candidate.

    Returns (current_params, current_metrics, best_params, best_metrics).
    """
    cur = current_config_params()
    cur_metrics = evaluate(cur, ticks, seeds)
    top = run_sweep(ticks=ticks, seeds=seeds, top=1)
    best_params, best_metrics = top[0]
    return cur, cur_metrics, best_params, best_metrics


def _fmt_metrics(m):
    return (f"ret {m['mean_return']:>6.2f}%  sharpe {m['mean_sharpe']:>5.2f}  "
            f"win {m['mean_win']:>4.1f}%  PF {m['mean_pf']:>4.2f}  "
            f"worst {m['worst_return']:>6.2f}%")


def main():
    ap = argparse.ArgumentParser(description="Strategy parameter sweep")
    ap.add_argument("--ticks", type=int, default=800)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--walk-forward", action="store_true",
                    help="In-sample/out-of-sample validation instead of a full sweep")
    ap.add_argument("--compare", action="store_true",
                    help="Compare the current shipping config vs. the best candidate")
    args = ap.parse_args()

    if args.compare:
        print(f"Comparing current config vs. best candidate "
              f"x {len(SEEDS)} seeds @ {args.ticks} ticks...\n")
        cur, cur_m, best, best_m = compare(ticks=args.ticks)
        print("CURRENT (shipping) config:")
        for k, v in cur.items():
            print(f"    {k:>18} = {v}")
        print(f"    -> {_fmt_metrics(cur_m)}\n")
        print("BEST candidate from grid:")
        for k, v in best.items():
            print(f"    {k:>18} = {v}")
        print(f"    -> {_fmt_metrics(best_m)}\n")
        delta = best_m["mean_sharpe"] - cur_m["mean_sharpe"]
        if delta <= 0.1:
            print(f"Sharpe delta {delta:+.2f}: current config is competitive; "
                  f"no change recommended (avoid overfitting).")
        else:
            print(f"Sharpe delta {delta:+.2f}: candidate looks better — "
                  f"VALIDATE with --walk-forward before changing defaults.")
        return

    if args.walk_forward:
        print(f"Walk-forward validation @ {args.ticks} ticks "
              f"(train: 1,7,42,99  test: 123,256,500)...\n")
        params, train_m, test_m = walk_forward(ticks=args.ticks)
        print("Best params chosen on TRAIN seeds:")
        for k, v in params.items():
            print(f"    {k:>18} = {v}")
        print()
        print(f"  TRAIN (in-sample)    : {_fmt_metrics(train_m)}")
        print(f"  TEST  (out-of-sample): {_fmt_metrics(test_m)}")
        drop = train_m["mean_sharpe"] - test_m["mean_sharpe"]
        verdict = ("GENERALISES WELL" if drop < 0.5
                   else "POSSIBLE OVERFIT" if drop < 1.0
                   else "LIKELY OVERFIT")
        print(f"\n  Sharpe drop train->test: {drop:+.2f}  =>  {verdict}")
        return

    print(f"Sweeping {len(list(itertools.product(*GRID.values())))} combos "
          f"x {len(SEEDS)} seeds @ {args.ticks} ticks...\n")
    top = run_sweep(ticks=args.ticks, top=args.top)

    print(f"{'conf':>5} {'TP_R':>5} {'actR':>5} {'give':>5} "
          f"{'ret%':>7} {'sharpe':>7} {'win%':>6} {'PF':>6} {'wret%':>7}")
    print("-" * 64)
    for params, m in top:
        print(f"{params['min_confidence']:>5} {params['take_profit_r']:>5} "
              f"{params['trail_activate_r']:>5} {params['trail_giveback']:>5} "
              f"{m['mean_return']:>7.2f} {m['mean_sharpe']:>7.2f} "
              f"{m['mean_win']:>6.1f} {m['mean_pf']:>6.2f} "
              f"{m['worst_return']:>7.2f}")
    print("\nBest by mean Sharpe (robust across all seeds) is the top row.")


if __name__ == "__main__":
    main()
