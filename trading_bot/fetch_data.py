"""Fetch REAL historical price data and write it as CSVs for the backtester.

Uses the free Yahoo Finance chart endpoint (no API key) to download daily OHLC
bars for the project's symbol universe and writes one ``<SYMBOL>.csv`` per
symbol (slashes in futures symbols written as ``_``) with an ``open/high/low/
close`` header — exactly the format ``CSVMarket`` expects.

Run:
    PYTHONPATH=. python3 -m trading_bot.fetch_data --out data_real --days 700
    PYTHONPATH=. python3 -m trading_bot.fetch_data --interval 1h --days 60

This is the bridge from "works against our simulator" to "works against real
market data" — the single most informative validation step for the strategy.
"""

import argparse
import csv
import json
import os
import ssl
import time
import urllib.request
import urllib.error

from trading_bot import config


# Project symbol -> Yahoo Finance ticker.
YAHOO_MAP = {
    "BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD", "SOLUSD": "SOL-USD",
    "AVAXUSD": "AVAX-USD",
    "AAPL": "AAPL", "TSLA": "TSLA", "NVDA": "NVDA", "GOOGL": "GOOGL",
    "MSFT": "MSFT", "AMZN": "AMZN", "META": "META", "AMD": "AMD",
    "QQQ": "QQQ", "SPY": "SPY", "IWM": "IWM", "TQQQ": "TQQQ",
    "/ES": "ES=F", "/NQ": "NQ=F", "/CL": "CL=F", "/GC": "GC=F",
}

_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _safe_name(symbol):
    return symbol.replace("/", "_")


def _ssl_ctx():
    ctx = ssl.create_default_context()
    # Sandboxes sometimes lack an up-to-date CA bundle; be permissive for a
    # read-only public data fetch.
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch_symbol(yahoo_ticker, days=700, interval="1d", retries=4):
    """Return list of dicts: [{open,high,low,close}, ...] in chronological order."""
    end = int(time.time())
    start = end - int(days) * 86400

    hosts = ["query2.finance.yahoo.com", "query1.finance.yahoo.com"]
    last_err = None
    payload = None
    for attempt in range(retries):
        host = hosts[attempt % len(hosts)]
        url = (f"https://{host}/v8/finance/chart/{yahoo_ticker}"
               f"?period1={start}&period2={end}&interval={interval}")
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx()) as resp:
                payload = json.loads(resp.read().decode())
            break
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code == 429:
                # Exponential backoff on rate limiting, alternating hosts.
                time.sleep(2 ** attempt * 2.0)
                continue
            raise
    if payload is None:
        raise last_err

    result = payload["chart"]["result"]
    if not result:
        return []
    q = result[0]["indicators"]["quote"][0]
    opens = q.get("open", [])
    highs = q.get("high", [])
    lows = q.get("low", [])
    closes = q.get("close", [])

    bars = []
    for o, h, l, c in zip(opens, highs, lows, closes):
        if c is None:
            continue  # skip holidays / missing bars
        bars.append({
            "open": o if o is not None else c,
            "high": h if h is not None else c,
            "low": l if l is not None else c,
            "close": c,
        })
    return bars


def write_csv(out_dir, symbol, bars):
    path = os.path.join(out_dir, _safe_name(symbol) + ".csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["open", "high", "low", "close"])
        for b in bars:
            w.writerow([round(b["open"], 6), round(b["high"], 6),
                        round(b["low"], 6), round(b["close"], 6)])
    return path


def fetch_all(out_dir, days=700, interval="1d", symbols=None, resume=True):
    symbols = symbols or config.SYMBOLS
    os.makedirs(out_dir, exist_ok=True)
    report = {}
    for symbol in symbols:
        ticker = YAHOO_MAP.get(symbol)
        if not ticker:
            report[symbol] = ("skipped", "no Yahoo mapping")
            continue
        existing = os.path.join(out_dir, _safe_name(symbol) + ".csv")
        if resume and os.path.exists(existing) and os.path.getsize(existing) > 50:
            report[symbol] = ("cached", existing)
            continue
        try:
            bars = fetch_symbol(ticker, days=days, interval=interval)
            if not bars:
                report[symbol] = ("empty", ticker)
                continue
            write_csv(out_dir, symbol, bars)
            report[symbol] = ("ok", len(bars))
        except Exception as exc:  # network / parse errors shouldn't abort the run
            report[symbol] = ("error", str(exc))
        time.sleep(1.5)  # be polite to the endpoint / avoid rate limiting
    return report


def main():
    ap = argparse.ArgumentParser(description="Fetch real historical data (Yahoo)")
    ap.add_argument("--out", type=str, default="data_real")
    ap.add_argument("--days", type=int, default=700)
    ap.add_argument("--interval", type=str, default="1d",
                    help="1d, 1h, 30m, 15m, 5m (intraday limited to recent days)")
    args = ap.parse_args()

    print(f"Fetching {len(config.SYMBOLS)} symbols "
          f"({args.interval}, ~{args.days}d) -> {args.out}/\n")
    report = fetch_all(args.out, days=args.days, interval=args.interval)

    ok = sum(1 for v in report.values() if v[0] == "ok")
    for symbol, (status, info) in report.items():
        mark = "✓" if status == "ok" else "•"
        print(f"  {mark} {symbol:<8} {status:<8} {info}")
    print(f"\n{ok}/{len(report)} symbols written to {args.out}/")
    if ok:
        print(f"\nNow run the backtest on real data:\n"
              f"    PYTHONPATH=. python3 -m trading_bot.backtest --csv-dir {args.out}")


if __name__ == "__main__":
    main()
