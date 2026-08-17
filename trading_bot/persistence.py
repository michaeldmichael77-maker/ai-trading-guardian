"""SQLite persistence layer.

Stores closed trades, daily sessions, equity-curve snapshots and the adaptive
Hive-Mind weights so the system's history and learning survive restarts.

Designed to be completely optional and failure-tolerant: any DB error is
swallowed and logged via the provided logger so persistence problems can never
take down the trading loop.
"""

import json
import os
import sqlite3
import threading
import time

# The DB location can be overridden with GUARDIAN_DB (e.g. tests point this at
# a temp file / :memory: so they never touch the production database).
DEFAULT_DB = os.environ.get(
    "GUARDIAN_DB",
    os.path.join(os.path.dirname(__file__), "data", "guardian.db"),
)


class Storage:
    def __init__(self, db_path=DEFAULT_DB, logger=print):
        self.db_path = db_path
        self.logger = logger
        self._lock = threading.Lock()
        self.enabled = True
        try:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self._init_schema()
        except Exception as exc:  # pragma: no cover - defensive
            self.enabled = False
            self.logger(f"Persistence disabled (init failed): {exc}")

    # ------------------------------------------------------------------ #
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._lock, self._connect() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT, entry REAL, exit REAL, size REAL,
                    pnl REAL, reason TEXT, ts REAL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started REAL, ended REAL, start_equity REAL,
                    end_equity REAL, daily_pnl REAL, trades INTEGER,
                    reason TEXT
                );
                CREATE TABLE IF NOT EXISTS equity_curve (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL, equity REAL
                );
                CREATE TABLE IF NOT EXISTS kv (
                    key TEXT PRIMARY KEY, value TEXT
                );
                """
            )

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #
    def record_trade(self, symbol, entry, exit_price, size, pnl, reason):
        if not self.enabled:
            return
        try:
            with self._lock, self._connect() as c:
                c.execute(
                    "INSERT INTO trades(symbol,entry,exit,size,pnl,reason,ts)"
                    " VALUES(?,?,?,?,?,?,?)",
                    (symbol, entry, exit_price, size, pnl, reason, time.time()),
                )
        except Exception as exc:  # pragma: no cover - defensive
            self.logger(f"record_trade failed: {exc}")

    def record_session(self, started, ended, start_equity, end_equity,
                       daily_pnl, trades, reason):
        if not self.enabled:
            return
        try:
            with self._lock, self._connect() as c:
                c.execute(
                    "INSERT INTO sessions(started,ended,start_equity,end_equity,"
                    "daily_pnl,trades,reason) VALUES(?,?,?,?,?,?,?)",
                    (started, ended, start_equity, end_equity, daily_pnl,
                     trades, reason),
                )
        except Exception as exc:  # pragma: no cover - defensive
            self.logger(f"record_session failed: {exc}")

    def record_equity(self, equity, ts=None):
        if not self.enabled:
            return
        try:
            with self._lock, self._connect() as c:
                c.execute("INSERT INTO equity_curve(ts,equity) VALUES(?,?)",
                          (ts or time.time(), equity))
        except Exception as exc:  # pragma: no cover - defensive
            self.logger(f"record_equity failed: {exc}")

    def save_weights(self, weights):
        if not self.enabled:
            return
        try:
            with self._lock, self._connect() as c:
                c.execute(
                    "INSERT INTO kv(key,value) VALUES('hive_weights',?)"
                    " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (json.dumps(weights),),
                )
        except Exception as exc:  # pragma: no cover - defensive
            self.logger(f"save_weights failed: {exc}")

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    def load_weights(self):
        if not self.enabled:
            return None
        try:
            with self._lock, self._connect() as c:
                row = c.execute(
                    "SELECT value FROM kv WHERE key='hive_weights'").fetchone()
                return json.loads(row["value"]) if row else None
        except Exception as exc:  # pragma: no cover - defensive
            self.logger(f"load_weights failed: {exc}")
            return None

    def recent_trades(self, limit=50):
        if not self.enabled:
            return []
        try:
            with self._lock, self._connect() as c:
                rows = c.execute(
                    "SELECT symbol,entry,exit,size,pnl,reason,ts FROM trades"
                    " ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
                return [dict(r) for r in rows]
        except Exception as exc:  # pragma: no cover - defensive
            self.logger(f"recent_trades failed: {exc}")
            return []

    def equity_history(self, limit=500):
        if not self.enabled:
            return []
        try:
            with self._lock, self._connect() as c:
                rows = c.execute(
                    "SELECT ts,equity FROM equity_curve ORDER BY id DESC"
                    " LIMIT ?", (limit,)).fetchall()
                return [dict(r) for r in reversed(rows)]
        except Exception as exc:  # pragma: no cover - defensive
            self.logger(f"equity_history failed: {exc}")
            return []

    def recent_sessions(self, limit=20):
        if not self.enabled:
            return []
        try:
            with self._lock, self._connect() as c:
                rows = c.execute(
                    "SELECT * FROM sessions ORDER BY id DESC LIMIT ?",
                    (limit,)).fetchall()
                return [dict(r) for r in rows]
        except Exception as exc:  # pragma: no cover - defensive
            self.logger(f"recent_sessions failed: {exc}")
            return []

    def lifetime_stats(self):
        """Aggregate stats across all persisted trades."""
        if not self.enabled:
            return {}
        try:
            with self._lock, self._connect() as c:
                row = c.execute(
                    "SELECT COUNT(*) n, "
                    "SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END) wins, "
                    "COALESCE(SUM(pnl),0) total_pnl "
                    "FROM trades").fetchone()
                n = row["n"] or 0
                wins = row["wins"] or 0
                return {
                    "lifetime_trades": n,
                    "lifetime_wins": wins,
                    "lifetime_win_rate": round(wins / n * 100, 1) if n else 0.0,
                    "lifetime_pnl": round(row["total_pnl"], 2),
                }
        except Exception as exc:  # pragma: no cover - defensive
            self.logger(f"lifetime_stats failed: {exc}")
            return {}
