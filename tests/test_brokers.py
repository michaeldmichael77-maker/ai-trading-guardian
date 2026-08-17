"""Tests for the broker adapter layer and safe mode switching."""

import pytest

from trading_bot import config
from trading_bot.brokers.simulator import SimulatorAdapter
from trading_bot.brokers.alpaca import AlpacaAdapter, PAPER_URL, LIVE_URL
from trading_bot.broker_manager import BrokerManager
from trading_bot.engine.portfolio import Portfolio
from trading_bot.engine.market import MarketSimulator


# --------------------------------------------------------------------------- #
# Simulator adapter
# --------------------------------------------------------------------------- #
def _sim():
    m = MarketSimulator(seed=1)
    p = Portfolio(balance=100_000.0)
    prices = {"AAPL": 100.0}
    return SimulatorAdapter(m, p, prices, logger=lambda *_: None), p, prices


def test_sim_adapter_not_live():
    sim, _, _ = _sim()
    assert sim.is_live is False
    assert sim.connect()["is_live"] is False


def test_sim_adapter_account_and_order():
    sim, p, prices = _sim()
    sim.submit_order("AAPL", 10, "buy")
    assert p.get_position("AAPL")["size"] == 10
    acct = sim.get_account()
    assert acct["cash"] == 100_000.0 - 1_000.0


def test_sim_adapter_close_all():
    sim, p, prices = _sim()
    sim.submit_order("AAPL", 5, "buy")
    assert sim.close_all_positions() == 1
    assert p.position_count() == 0


# --------------------------------------------------------------------------- #
# Alpaca adapter (mocked transport — no network/keys needed)
# --------------------------------------------------------------------------- #
@pytest.fixture
def mock_alpaca(monkeypatch):
    def fake_request(self, method, url, body=None, timeout=15):
        if url.endswith("/account"):
            return {"account_number": "PA1", "status": "ACTIVE",
                    "cash": "50000", "equity": "50000",
                    "buying_power": "50000", "currency": "USD"}
        if url.endswith("/positions") and method == "GET":
            return [{"symbol": "AAPL", "qty": "3", "avg_entry_price": "100",
                     "market_value": "330", "unrealized_pl": "30"}]
        if url.endswith("/orders") and method == "POST":
            return {"id": "o1", "symbol": body["symbol"], "qty": body["qty"],
                    "side": body["side"], "status": "accepted"}
        return {}
    monkeypatch.setattr(AlpacaAdapter, "_request", fake_request)


def test_alpaca_paper_uses_paper_url(mock_alpaca):
    a = AlpacaAdapter("k", "s", paper=True, logger=lambda *_: None)
    assert a.base_url == PAPER_URL
    assert a.is_live is False


def test_alpaca_live_uses_live_url(mock_alpaca):
    a = AlpacaAdapter("k", "s", paper=False, logger=lambda *_: None)
    assert a.base_url == LIVE_URL
    assert a.is_live is True


def test_alpaca_connect_and_account(mock_alpaca):
    a = AlpacaAdapter("k", "s", paper=True, logger=lambda *_: None)
    info = a.connect()
    assert info["connected"] is True
    assert a.get_account()["cash"] == 50_000.0


def test_alpaca_positions_parsed(mock_alpaca):
    a = AlpacaAdapter("k", "s", paper=True, logger=lambda *_: None)
    pos = a.get_positions()
    assert pos[0]["symbol"] == "AAPL"
    assert pos[0]["side"] == "LONG"


def test_alpaca_missing_keys_raises():
    from trading_bot.brokers.base import BrokerError
    a = AlpacaAdapter("", "", paper=True, logger=lambda *_: None)
    with pytest.raises(BrokerError):
        a.connect()


# --------------------------------------------------------------------------- #
# Broker manager safe switching
# --------------------------------------------------------------------------- #
@pytest.fixture
def manager(mock_alpaca, monkeypatch):
    sim, _, _ = _sim()
    monkeypatch.setattr(config, "ALPACA_API_KEY_ID", "k")
    monkeypatch.setattr(config, "ALPACA_API_SECRET_KEY", "s")
    return BrokerManager(sim, logger=lambda *_: None)


def test_default_mode_is_sim(manager):
    assert manager.mode == "sim"
    assert manager.is_live() is False


def test_switch_to_paper(manager):
    ok, info = manager.switch("paper")
    assert ok is True
    assert manager.mode == "paper"
    assert manager.is_live() is False


def test_switch_to_live_blocked_without_optin(manager, monkeypatch):
    monkeypatch.setattr(config, "ALLOW_LIVE_TRADING", False)
    ok, info = manager.switch("live")
    assert ok is False
    assert "locked" in info["error"].lower()
    assert manager.is_live() is False   # stayed safe


def test_switch_to_live_allowed_with_optin(manager, monkeypatch):
    monkeypatch.setattr(config, "ALLOW_LIVE_TRADING", True)
    ok, info = manager.switch("live")
    assert ok is True
    assert manager.is_live() is True


def test_switch_paper_without_keys_fails(monkeypatch):
    sim, _, _ = _sim()
    monkeypatch.setattr(config, "ALPACA_API_KEY_ID", "")
    monkeypatch.setattr(config, "ALPACA_API_SECRET_KEY", "")
    m = BrokerManager(sim, logger=lambda *_: None)
    ok, info = m.switch("paper")
    assert ok is False
    assert "key" in info["error"].lower()


def test_switch_back_to_sim(manager):
    manager.switch("paper")
    ok, info = manager.switch("sim")
    assert ok is True
    assert manager.mode == "sim"
    assert manager.is_live() is False


# --------------------------------------------------------------------------- #
# Set keys + test connection (the dashboard "paste keys" + "Test" flow)
# --------------------------------------------------------------------------- #
def test_set_keys_stores_and_reports(monkeypatch):
    sim, _, _ = _sim()
    monkeypatch.setattr(config, "ALPACA_API_KEY_ID", "")
    monkeypatch.setattr(config, "ALPACA_API_SECRET_KEY", "")
    m = BrokerManager(sim, logger=lambda *_: None)
    assert m.set_keys("mykey", "mysecret") is True
    assert config.ALPACA_API_KEY_ID == "mykey"
    assert config.ALPACA_API_SECRET_KEY == "mysecret"


def test_set_keys_missing_returns_false(monkeypatch):
    sim, _, _ = _sim()
    monkeypatch.setattr(config, "ALPACA_API_KEY_ID", "")
    monkeypatch.setattr(config, "ALPACA_API_SECRET_KEY", "")
    m = BrokerManager(sim, logger=lambda *_: None)
    assert m.set_keys("", "") is False


def test_test_connection_no_keys(monkeypatch):
    sim, _, _ = _sim()
    monkeypatch.setattr(config, "ALPACA_API_KEY_ID", "")
    monkeypatch.setattr(config, "ALPACA_API_SECRET_KEY", "")
    m = BrokerManager(sim, logger=lambda *_: None)
    res = m.test_connection()
    assert res["ok"] is False
    assert "key" in res["message"].lower()


def test_test_connection_success(manager):
    # manager fixture has mocked Alpaca + keys set.
    res = manager.test_connection(mode="paper")
    assert res["ok"] is True
    assert "PAPER" in res["environment"]
    assert res["account_number"] == "PA1"
    assert "buying power" in res["message"].lower()
