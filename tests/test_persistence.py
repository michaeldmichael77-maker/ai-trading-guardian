"""Tests for the SQLite persistence layer (uses a temp DB, never the real one)."""

import os
import tempfile

import pytest

from trading_bot.persistence import Storage


@pytest.fixture
def store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = Storage(db_path=path, logger=lambda *_: None)
    yield s
    os.remove(path)


def test_storage_enabled(store):
    assert store.enabled is True


def test_record_and_read_trades(store):
    store.record_trade("AAPL", 100.0, 110.0, 5, 50.0, "signal")
    store.record_trade("TSLA", 200.0, 190.0, 2, -20.0, "STOP-LOSS")
    trades = store.recent_trades()
    assert len(trades) == 2
    assert trades[0]["symbol"] == "TSLA"   # most recent first


def test_lifetime_stats(store):
    store.record_trade("A", 1, 2, 1, 100.0, "x")
    store.record_trade("B", 1, 2, 1, -40.0, "x")
    store.record_trade("C", 1, 2, 1, 60.0, "x")
    s = store.lifetime_stats()
    assert s["lifetime_trades"] == 3
    assert s["lifetime_wins"] == 2
    assert s["lifetime_pnl"] == 120.0
    assert s["lifetime_win_rate"] == 66.7


def test_save_and_load_weights(store):
    weights = {"MA_Cross": 1.2, "RSI": 0.8}
    store.save_weights(weights)
    loaded = store.load_weights()
    assert loaded == weights


def test_load_weights_none_when_empty(store):
    assert store.load_weights() is None


def test_weights_upsert_overwrites(store):
    store.save_weights({"RSI": 1.0})
    store.save_weights({"RSI": 1.5})
    assert store.load_weights() == {"RSI": 1.5}


def test_equity_history_order(store):
    store.record_equity(100.0, ts=1)
    store.record_equity(110.0, ts=2)
    hist = store.equity_history()
    assert [h["equity"] for h in hist] == [100.0, 110.0]   # chronological


def test_record_session(store):
    store.record_session(1.0, 2.0, 100000, 101000, 1000, 5, "profit target")
    sessions = store.recent_sessions()
    assert len(sessions) == 1
    assert sessions[0]["daily_pnl"] == 1000


def test_disabled_storage_is_safe():
    """A storage that failed to init must no-op without raising."""
    s = Storage(db_path="/nonexistent_dir_xyz/sub/db.sqlite",
                logger=lambda *_: None)
    assert s.enabled is False
    # None of these should raise.
    s.record_trade("A", 1, 2, 1, 1.0, "x")
    s.record_equity(100.0)
    s.save_weights({"RSI": 1.0})
    assert s.load_weights() is None
    assert s.recent_trades() == []
    assert s.lifetime_stats() == {}
