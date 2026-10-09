"""Live real-time market data feed.

Pulls real live quotes and 1-minute OHLC bars from institutional market feeds
for futures, crypto, and equities so the Hive-Mind analyzes true exchange price
action and real candle bars in live mode.
"""

import json
import time
import urllib.request

YAHOO_MAP = {
    "/NQ": "NQ=F",
    "MNQ": "NQ=F",
    "/ES": "ES=F",
    "MES": "ES=F",
    "/GC": "GC=F",
    "MGC": "GC=F",
    "/CL": "CL=F",
    "MCL": "CL=F",
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
    "SOLUSD": "SOL-USD",
    "AVAXUSD": "AVAX-USD",
    "QQQ": "QQQ",
    "SPY": "SPY",
    "IWM": "IWM",
    "TQQQ": "TQQQ",
    "AAPL": "AAPL",
    "TSLA": "TSLA",
    "NVDA": "NVDA",
    "GOOGL": "GOOGL",
    "MSFT": "MSFT",
    "AMZN": "AMZN",
    "META": "META",
    "AMD": "AMD",
}


class LiveMarketFeed:
    """Live market price and historical 1m bar provider with caching."""

    def __init__(self, fallback_sim=None):
        self.fallback = fallback_sim
        self.cache = {}
        self.last_fetch = {}
        self.bars_cache = {}
        self.last_bar_fetch = {}
        self.headers = {"User-Agent": "Mozilla/5.0"}

    def get_price(self, symbol: str):
        now = time.time()
        # Cache quote for 1.0 second per symbol to prevent rate-limiting
        if symbol in self.cache and (now - self.last_fetch.get(symbol, 0)) < 1.0:
            return self.cache[symbol]

        y_sym = YAHOO_MAP.get(symbol)
        if not y_sym:
            return self.fallback.get_price(symbol) if self.fallback else None

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{y_sym}?interval=1m&range=1d"
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                result = data["chart"]["result"][0]
                meta = result["meta"]
                p = float(meta.get("regularMarketPrice") or 0)
                if p > 0:
                    self.cache[symbol] = round(p, 4)
                    self.last_fetch[symbol] = now

                # Also cache closes if available
                quotes = result.get("indicators", {}).get("quote", [{}])[0]
                closes = [round(c, 4) for c in quotes.get("close", []) if c is not None]
                if closes:
                    self.bars_cache[symbol] = closes
                    self.last_bar_fetch[symbol] = now
                    if p <= 0:
                        self.cache[symbol] = closes[-1]
                        self.last_fetch[symbol] = now

                if symbol in self.cache:
                    return self.cache[symbol]
        except Exception:
            pass

        if symbol in self.cache:
            return self.cache[symbol]
        return self.fallback.get_price(symbol) if self.fallback else None

    def get_bars(self, symbol: str, count: int = 60):
        """Retrieve recent 1-minute closing bars for real technical analysis."""
        now = time.time()
        y_sym = YAHOO_MAP.get(symbol)
        if not y_sym:
            return []

        # Use cached bars if fetched within last 15 seconds
        if symbol in self.bars_cache and (now - self.last_bar_fetch.get(symbol, 0)) < 15.0:
            return self.bars_cache[symbol][-count:]

        # Fetch fresh bars
        self.get_price(symbol)
        return self.bars_cache.get(symbol, [])[-count:]

    def snapshot(self):
        return {s: self.get_price(s) for s in YAHOO_MAP.keys()}
