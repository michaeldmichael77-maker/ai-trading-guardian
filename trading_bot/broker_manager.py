"""Broker mode manager.

Holds the currently-active broker adapter and handles SAFE switching between:
    sim  -> simulator (fake prices/money)
    paper-> Alpaca paper (real prices, fake money)
    live -> Alpaca live (REAL money)  [hard-gated]

It never silently connects to real money: switching to "live" requires both
valid keys AND the explicit ALLOW_LIVE_TRADING guard, and returns clear errors
otherwise. Everything routes through this so the safety rails always apply.
"""

from trading_bot import config
from trading_bot.brokers.base import BrokerError
from trading_bot.brokers.simulator import SimulatorAdapter
from trading_bot.brokers.alpaca import AlpacaAdapter


class BrokerManager:
    def __init__(self, sim_adapter, notifier=None, logger=print):
        self.sim_adapter = sim_adapter
        self.notifier = notifier
        self.logger = logger
        self.mode = "sim"
        self.adapter = sim_adapter
        self.last_error = None

    # ------------------------------------------------------------------ #
    def _alert(self, title, msg, level="INFO"):
        if self.notifier:
            self.notifier.notify(title, msg, level=level)
        else:
            self.logger(f"[{level}] {title} — {msg}")

    def is_live(self):
        return self.adapter.is_live

    def set_keys(self, key_id, secret_key):
        """Store Alpaca keys (entered in the dashboard) for this session.

        Saved in memory only — never written to disk. Lets you connect without
        using the terminal. (For a permanent setup, use environment variables.)
        """
        config.ALPACA_API_KEY_ID = (key_id or "").strip()
        config.ALPACA_API_SECRET_KEY = (secret_key or "").strip()
        has = bool(config.ALPACA_API_KEY_ID and config.ALPACA_API_SECRET_KEY)
        return has

    def test_connection(self, mode=None):
        """Check that the keys work, WITHOUT changing your current mode.

        Returns a friendly dict telling you exactly what happened: connected or
        not, which account, how much buying power, and any error message.
        """
        mode = (mode or ("live" if self.is_live() else "paper")).lower()
        key = config.ALPACA_API_KEY_ID
        secret = config.ALPACA_API_SECRET_KEY
        if not key or not secret:
            return {"ok": False,
                    "message": "No API keys entered yet. Paste your Alpaca Key "
                               "ID and Secret Key, then try again."}
        paper = (mode != "live")
        probe = AlpacaAdapter(key, secret, paper=paper, logger=self.logger)
        try:
            acct = probe.get_account()
            return {
                "ok": True,
                "environment": "PAPER (fake money)" if paper else "LIVE (real money)",
                "account_number": acct.get("account_number"),
                "status": acct.get("status"),
                "cash": acct.get("cash"),
                "buying_power": acct.get("buying_power"),
                "message": (f"✅ Connected to your Alpaca "
                            f"{'paper' if paper else 'LIVE'} account "
                            f"{acct.get('account_number')} — buying power "
                            f"${acct.get('buying_power'):,.2f}."),
            }
        except BrokerError as exc:
            return {"ok": False,
                    "message": f"❌ Could not connect: {exc}"}

    def switch(self, mode):
        """Switch trading mode. Returns (ok: bool, info: dict)."""
        mode = (mode or "").lower().strip()
        if mode not in ("sim", "paper", "live"):
            return False, {"error": f"Unknown mode '{mode}'."}

        if mode == "sim":
            self.adapter = self.sim_adapter
            self.mode = "sim"
            self.last_error = None
            self._alert("🧪 Switched to SIMULATOR",
                        "Fake prices, fake money. Totally safe for testing.",
                        level="INFO")
            return True, {"mode": "sim", "is_live": False,
                          "name": self.sim_adapter.name}

        # paper or live -> need Alpaca keys
        key = config.ALPACA_API_KEY_ID
        secret = config.ALPACA_API_SECRET_KEY
        if not key or not secret:
            msg = ("No Alpaca API keys found. Set ALPACA_API_KEY_ID and "
                   "ALPACA_API_SECRET_KEY (from app.alpaca.markets) and restart.")
            self.last_error = msg
            return False, {"error": msg}

        if mode == "live":
            # HARD gate: refuse real money unless explicitly allowed.
            if not config.ALLOW_LIVE_TRADING:
                msg = ("LIVE trading is locked. To enable REAL-money trading you "
                       "must set GUARDIAN_ALLOW_LIVE=1 in your environment and "
                       "restart. This is a deliberate safety gate.")
                self.last_error = msg
                self._alert("⛔ LIVE trading blocked (safety gate)", msg,
                            level="WARNING")
                return False, {"error": msg}

        paper = (mode == "paper")
        adapter = AlpacaAdapter(key, secret, paper=paper, logger=self.logger)
        try:
            info = adapter.connect()
        except BrokerError as exc:
            self.last_error = str(exc)
            self._alert("❌ Could not connect to Alpaca", str(exc),
                        level="WARNING")
            return False, {"error": str(exc)}

        self.adapter = adapter
        self.mode = mode
        self.last_error = None
        if mode == "live":
            self._alert("🔴 LIVE TRADING ACTIVE — REAL MONEY",
                        f"Connected to your LIVE Alpaca account "
                        f"({info.get('account_number')}). Real orders will use "
                        f"real money. Your daily loss limit and kill switch are "
                        f"active.", level="CRITICAL")
        else:
            self._alert("📝 Switched to PAPER trading (Alpaca)",
                        f"Connected to your Alpaca paper account "
                        f"({info.get('account_number')}). REAL market prices, "
                        f"FAKE money — safe to test.", level="SUCCESS")
        return True, info

    def status(self):
        return {
            "mode": self.mode,
            "broker": self.adapter.name,
            "is_live": self.adapter.is_live,
            "connected": self.adapter.connected,
            "live_allowed": config.ALLOW_LIVE_TRADING,
            "has_keys": bool(config.ALPACA_API_KEY_ID and config.ALPACA_API_SECRET_KEY),
            "last_error": self.last_error,
        }
