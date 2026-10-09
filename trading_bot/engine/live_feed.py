"""Live real-time market data feed.

Pulls real live quotes from financial market feeds for futures, crypto,
and equities so the Hive-Mind analyzes true exchange price action in live mode.
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
    """Live market price provider with 1-second caching."""

    def __init__(self, fallback_sim=None):
        self.fallback = fallback_sim
        self.cache = {}
        self.last_fetch = {}
        self.headers = {"User-Agent": "Mozilla/5.0"}

    def get_price(self, symbol: str):
        now = time.time()
        # Cache for 1.0 second to prevent API rate limiting
        if symbol in self.cache and (now - self.last_fetch.get(symbol, 0)) < 1.0:
            return self.cache[symbol]

        y_sym = YAHOO_MAP.get(symbol)
        if not y_sym:
            return self.fallback.get_price(symbol) if self.fallback else None

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{y_sym}?interval=1m&range=1d"
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                meta = data["chart"]["result"][0]["meta"]
                p = float(meta.get("regularMarketPrice") or 0)
                if p > 0:
                    self.cache[symbol] = round(p, 4)
                    self.last_fetch[symbol] = now
                    return self.cache[symbol]
        except Exception:
            pass

        if symbol in self.cache:
            return self.cache[symbol]
        return self.fallback.get_price(symbol) if self.fallback else None

    def snapshot(self):
        return {s: self.get_price(s) for s in YAHOO_MAP.keys()}
