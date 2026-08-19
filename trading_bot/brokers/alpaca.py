"""Alpaca broker adapter (REST, stdlib only — no extra dependencies).

Supports BOTH Alpaca environments:
  * PAPER  -> https://paper-api.alpaca.markets   (real market data, FAKE money)
  * LIVE   -> https://api.alpaca.markets          (REAL money)

You get free API keys at https://app.alpaca.markets (create a Paper account,
open the API Keys panel, generate a key + secret).

SAFETY: ``is_live`` is True ONLY when pointed at the live domain. The rest of
the app uses that flag to show big warnings and require confirmation before any
real-money action. Paper is the default everywhere.
"""

import json
import ssl
import time
import urllib.error
import urllib.request

PAPER_URL = "https://paper-api.alpaca.markets"
LIVE_URL = "https://api.alpaca.markets"
DATA_URL = "https://data.alpaca.markets"

from trading_bot.brokers.base import BrokerAdapter, BrokerError


class AlpacaAdapter(BrokerAdapter):
    def __init__(self, key_id, secret_key, paper=True, logger=print):
        self.key_id = (key_id or "").strip()
        self.secret_key = (secret_key or "").strip()
        self.paper = paper
        self.logger = logger
        self.base_url = PAPER_URL if paper else LIVE_URL
        self.name = f"Alpaca ({'paper' if paper else 'LIVE'})"
        self.is_live = not paper
        self.connected = False
        self._account_cache = None

    # ------------------------------------------------------------------ #
    def _headers(self):
        return {
            "APCA-API-KEY-ID": self.key_id,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json",
            "accept": "application/json",
        }

    def _request(self, method, url, body=None, timeout=15):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers=self._headers())
        ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode()
            except Exception:
                pass
            if exc.code in (401, 403):
                raise BrokerError(
                    "Authentication failed (check your API key/secret and that "
                    "they match the paper/live environment). " + detail)
            raise BrokerError(f"Alpaca API error {exc.code}: {detail}")
        except urllib.error.URLError as exc:
            raise BrokerError(f"Network error reaching Alpaca: {exc.reason}")

    def _trade(self, method, path, body=None):
        return self._request(method, self.base_url + "/v2" + path, body)

    # ------------------------------------------------------------------ #
    def connect(self):
        if not self.key_id or not self.secret_key:
            raise BrokerError("Missing Alpaca API key or secret.")
        acct = self._trade("GET", "/account")
        self.connected = True
        self._account_cache = acct
        self.logger(f"Connected to {self.name}: account {acct.get('account_number')} "
                    f"status={acct.get('status')}")
        return {
            "connected": True,
            "name": self.name,
            "is_live": self.is_live,
            "account_number": acct.get("account_number"),
            "status": acct.get("status"),
            "cash": float(acct.get("cash", 0) or 0),
            "equity": float(acct.get("equity", 0) or 0),
        }

    # ------------------------------------------------------------------ #
    def get_account(self):
        acct = self._trade("GET", "/account")
        self._account_cache = acct
        return {
            "cash": float(acct.get("cash", 0) or 0),
            "equity": float(acct.get("equity", 0) or 0),
            "buying_power": float(acct.get("buying_power", 0) or 0),
            "currency": acct.get("currency", "USD"),
            "status": acct.get("status"),
            "account_number": acct.get("account_number"),
        }

    def get_positions(self):
        rows = self._trade("GET", "/positions")
        out = []
        for p in rows:
            qty = float(p.get("qty", 0) or 0)
            out.append({
                "symbol": p.get("symbol"),
                "qty": abs(qty),
                "avg_price": float(p.get("avg_entry_price", 0) or 0),
                "side": "LONG" if qty >= 0 else "SHORT",
                "market_value": float(p.get("market_value", 0) or 0),
                "unrealised_pnl": float(p.get("unrealized_pl", 0) or 0),
            })
        return out

    def get_price(self, symbol):
        """Latest trade price via the market-data API."""
        url = f"{DATA_URL}/v2/stocks/{urllib.parse.quote(symbol)}/trades/latest"
        try:
            data = self._request("GET", url)
            return float(data.get("trade", {}).get("p")) if data.get("trade") else None
        except BrokerError:
            return None

    # ------------------------------------------------------------------ #
    def submit_order(self, symbol, qty, side, order_type="market",
                     time_in_force="day"):
        body = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
        }
        order = self._trade("POST", "/orders", body)
        self.logger(f"[{self.name}] order {side} {qty} {symbol} -> "
                    f"id={order.get('id')} status={order.get('status')}")
        return {
            "id": order.get("id"),
            "symbol": order.get("symbol"),
            "qty": order.get("qty"),
            "side": order.get("side"),
            "status": order.get("status"),
            "submitted_at": order.get("submitted_at"),
        }

    def close_position(self, symbol):
        try:
            res = self._trade("DELETE", f"/positions/{urllib.parse.quote(symbol)}")
            return res
        except BrokerError as exc:
            self.logger(f"close_position {symbol} failed: {exc}")
            return None

    def close_all_positions(self):
        try:
            res = self._request("DELETE", self.base_url + "/v2/positions?cancel_orders=true")
            return len(res) if isinstance(res, list) else 0
        except BrokerError as exc:
            self.logger(f"close_all_positions failed: {exc}")
            return 0


# urllib.parse is needed by get_price/close_position; import after class def to
# keep the top tidy (and avoid a hard dependency if those paths are unused).
import urllib.parse  # noqa: E402
