"""Export a price series to per-symbol CSV files.

Two uses:
  * Generate sample data so the CSV replay path can be demoed without a paid
    market-data feed.
  * Serve as a template for the format CSVMarket expects when you drop in REAL
    historical data (one <SYMBOL>.csv per symbol with a ``close`` column).

Run:
    PYTHONPATH=. python3 -m trading_bot.export_csv --out data_csv --bars 1200
"""

import argparse
import csv
import os

from trading_bot import config
from trading_bot.engine.market import MarketSimulator


def _safe_name(symbol):
    return symbol.replace("/", "_")


def export(out_dir, bars=1200, seed=42, symbols=None):
    symbols = symbols or config.SYMBOLS
    os.makedirs(out_dir, exist_ok=True)
    market = MarketSimulator(seed=seed)
    # Pre-roll the whole series per symbol.
    series = {s: [] for s in symbols}
    for _ in range(bars):
        for s in symbols:
            series[s].append(market.get_price(s))

    for s in symbols:
        path = os.path.join(out_dir, _safe_name(s) + ".csv")
        with open(path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["close"])
            for px in series[s]:
                writer.writerow([px])
    return out_dir, len(symbols), bars


def main():
    ap = argparse.ArgumentParser(description="Export sample price CSVs")
    ap.add_argument("--out", type=str, default="data_csv")
    ap.add_argument("--bars", type=int, default=1200)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    out, n, bars = export(args.out, bars=args.bars, seed=args.seed)
    print(f"Wrote {n} symbol files x {bars} bars to {out}/")


if __name__ == "__main__":
    main()
