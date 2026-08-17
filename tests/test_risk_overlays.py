"""Tests for heat/correlation, drawdown recovery and the guardian."""

from trading_bot.correlation_heat import PortfolioHeatMonitor
from trading_bot.drawdown_recovery import DrawdownRecovery
from trading_bot.engine.portfolio import Portfolio
from trading_bot.engine.guardian import Guardian


# --------------------------------------------------------------------------- #
# Portfolio heat / correlation
# --------------------------------------------------------------------------- #
def test_heat_increases_with_positions():
    m = PortfolioHeatMonitor()
    r = m.compute({"AAPL": {}, "MSFT": {}}, equity=100_000.0, per_trade_stop=50.0)
    # 2 positions * $50 risk / 100k = 0.001 -> 0.1%
    assert r["heat_pct"] == 0.1


def test_correlation_cluster_high_for_four_crypto():
    m = PortfolioHeatMonitor()
    crypto = {"BTCUSD": {}, "ETHUSD": {}, "SOLUSD": {}, "AVAXUSD": {}}
    r = m.compute(crypto, equity=100_000.0, per_trade_stop=50.0)
    assert r["correlation_risk"] == "HIGH"


def test_can_add_position_blocks_cluster_overconcentration():
    m = PortfolioHeatMonitor()
    crypto = {"BTCUSD": {}, "ETHUSD": {}, "SOLUSD": {}}
    allowed, reason = m.can_add_position(
        crypto, equity=100_000.0, per_trade_stop=50.0, symbol="AVAXUSD")
    assert allowed is False
    assert "cluster" in reason.lower()


def test_can_add_position_allows_diversified():
    m = PortfolioHeatMonitor()
    positions = {"BTCUSD": {}, "AAPL": {}}
    allowed, _ = m.can_add_position(
        positions, equity=100_000.0, per_trade_stop=50.0, symbol="QQQ")
    assert allowed is True


def test_max_open_positions_blocks():
    m = PortfolioHeatMonitor()
    # 6 positions across different groups hits MAX_OPEN_POSITIONS
    positions = {s: {} for s in
                 ["BTCUSD", "AAPL", "QQQ", "/CL", "ETHUSD", "MSFT"]}
    allowed, reason = m.can_add_position(
        positions, equity=100_000.0, per_trade_stop=50.0, symbol="TSLA")
    assert allowed is False


# --------------------------------------------------------------------------- #
# Drawdown recovery ladder
# --------------------------------------------------------------------------- #
def test_drawdown_normal_mode():
    d = DrawdownRecovery()
    r = d.update(equity=100_000.0, peak_equity=100_000.0)
    assert r["mode"] == "NORMAL"
    assert r["risk_multiplier"] == 1.0


def test_drawdown_cautious():
    d = DrawdownRecovery()
    r = d.update(equity=97_500.0, peak_equity=100_000.0)   # 2.5% dd
    assert r["mode"] == "CAUTIOUS"
    assert r["risk_multiplier"] == 0.75


def test_drawdown_lockdown():
    d = DrawdownRecovery()
    r = d.update(equity=93_000.0, peak_equity=100_000.0)   # 7% dd
    assert r["mode"] == "LOCKDOWN"
    assert r["risk_multiplier"] == 0.25
    assert r["confidence_bonus"] > 0


def test_drawdown_recovers_to_normal():
    d = DrawdownRecovery()
    d.update(equity=93_000.0, peak_equity=100_000.0)       # lockdown
    r = d.update(equity=100_000.0, peak_equity=100_000.0)  # recovered
    assert r["mode"] == "NORMAL"


# --------------------------------------------------------------------------- #
# Guardian per-trade stop detection
# --------------------------------------------------------------------------- #
def test_guardian_detects_per_trade_stop_breach():
    p = Portfolio(balance=100_000.0)
    p.execute_buy("AAPL", 100.0, 100)       # 100 shares
    g = Guardian(p, per_trade_stop=50.0)
    # price drops to 99.0 -> loss = (100-99)*100 = 100 >= 50
    breached = g.check_per_trade_stops({"AAPL": 99.0})
    assert "AAPL" in breached


def test_guardian_no_breach_within_stop():
    p = Portfolio(balance=100_000.0)
    p.execute_buy("AAPL", 100.0, 10)        # small position
    g = Guardian(p, per_trade_stop=50.0)
    # price 99 -> loss (100-99)*10 = 10 < 50
    breached = g.check_per_trade_stops({"AAPL": 99.0})
    assert breached == []
