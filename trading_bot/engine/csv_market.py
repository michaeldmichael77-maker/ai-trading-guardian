"""Historical CSV market replay.

A drop-in replacement for ``MarketSimulator`` that replays REAL (or any
recorded) price history instead of generating synthetic data. This is the
highest-signal validation step: the strategy's edge against the simulator is
only as meaningful as the simulator; replaying genuine market data tells you
far more.

Interface parity with MarketSimulator
-------------------------------------
    get_price(symbol) -> advance one bar for that symbol and return its close
    snapshot()        -> current price for every symbol (no advance)

Expected data layout
---------------------
A directory containing one CSV per symbol named ``<SYMBOL>.csv`` (slashes in
futures symbols like ``/ES`` are written as ``_ES.csv``). Each file needs a
header with at least a ``close`` column (case-insensitive); ``open/high/low``
are optional and ignored for now. Rows are assumed to be in chronological
order.
"""

import csv
import os


def _safe_name(symbol):
    return symbol.replace("/", "_")


class CSVMarket:
    def __init__(self, data_dir, symbols=None):
        self.data_dir = data_dir
        self.series = {}          # symbol -> list[float] closes
        self._idx = {}            # symbol -> current row pointer
        self.last = {}            # symbol -> last returned price

        discovered = []
        wanted = symbols
        if wanted is None:
            # Discover every *.csv in the directory.
            wanted = []
            for fname in sorted(os.listdir(data_dir)):
                if fname.lower().endswith(".csv"):
                    wanted.append(fname[:-4].replace("_", "/")
                                  if fname.startswith("_") else fname[:-4])

        for symbol in wanted:
            path = os.path.join(data_dir, _safe_name(symbol) + ".csv")
            if not os.path.exists(path):
                continue
            closes = self._load_closes(path)
            if closes:
                self.series[symbol] = closes
                self._idx[symbol] = 0
                self.last[symbol] = closes[0]
                discovered.append(symbol)

        self.symbols = discovered
        if not self.symbols:
            raise ValueError(f"No usable CSV price files found in {data_dir!r}")

    @staticmethod
    def _load_closes(path):
        closes = []
        with open(path, newline="") as fh:
            reader = csv.DictReader(fh)
            # Normalise header lookup to be case-insensitive.
            field_map = {k.lower(): k for k in (reader.fieldnames or [])}
            close_key = field_map.get("close") or field_map.get("price")
            if close_key is None:
                return closes
            for row in reader:
                try:
                    closes.append(float(row[close_key]))
                except (TypeError, ValueError):
                    continue
        return closes

    def length(self):
        """Number of bars available (limited by the shortest series)."""
        if not self.series:
            return 0
        return min(len(v) for v in self.series.values())

    def get_price(self, symbol):
        series = self.series.get(symbol)
        if not series:
            return None
        i = self._idx[symbol]
        if i >= len(series):
            # Past the end: hold the final price (flat).
            price = series[-1]
        else:
            price = series[i]
            self._idx[symbol] = i + 1
        self.last[symbol] = price
        return round(price, 4)

    def snapshot(self):
        return {s: round(p, 4) for s, p in self.last.items()}
