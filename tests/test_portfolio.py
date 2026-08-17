"""Tests for portfolio accounting - the area most prone to P&L bugs."""

from trading_bot.engine.portfolio import Portfolio


def test_buy_reduces_cash_and_opens_position():
    p = Portfolio(balance=100_000.0)
    p.execute_buy("AAPL", 100.0, 10)
    assert p.balance == 100_000.0 - 1_000.0
    pos = p.get_position("AAPL")
    assert pos["size"] == 10
    assert pos["avg_price"] == 100.0
    assert pos["side"] == "LONG"
    assert p.position_count() == 1


def test_sell_realises_pnl_and_closes():
    p = Portfolio(balance=100_000.0)
    p.execute_buy("AAPL", 100.0, 10)
    result = p.execute_sell("AAPL", 110.0, 10)
    assert result["pnl"] == 100.0          # (110-100)*10
    assert p.daily_pnl == 100.0
    assert p.position_count() == 0
    # Cash: 100k -1000 (buy) +1100 (sell) = 100,100
    assert p.balance == 100_100.0


def test_partial_sell_keeps_remaining_size():
    p = Portfolio(balance=100_000.0)
    p.execute_buy("AAPL", 100.0, 10)
    p.execute_sell("AAPL", 105.0, 4)
    pos = p.get_position("AAPL")
    assert pos["size"] == 6
    assert p.position_count() == 1


def test_averaging_up_updates_avg_price():
    p = Portfolio(balance=100_000.0)
    p.execute_buy("AAPL", 100.0, 10)
    p.execute_buy("AAPL", 120.0, 10)
    pos = p.get_position("AAPL")
    assert pos["size"] == 20
    assert pos["avg_price"] == 110.0       # weighted average


def test_sell_with_no_position_returns_none():
    p = Portfolio(balance=100_000.0)
    assert p.execute_sell("AAPL", 100.0, 5) is None


def test_unrealised_pnl_and_equity():
    p = Portfolio(balance=100_000.0)
    p.execute_buy("AAPL", 100.0, 10)       # cash now 99,000
    prices = {"AAPL": 130.0}
    assert p.unrealised_pnl(prices) == 300.0
    # equity = cash + market value = 99,000 + 1,300 = 100,300
    assert p.equity(prices) == 100_300.0


def test_equity_equals_balance_when_flat():
    p = Portfolio(balance=100_000.0)
    assert p.equity({}) == 100_000.0


def test_drawdown_tracking():
    p = Portfolio(balance=100_000.0)
    p.execute_buy("AAPL", 100.0, 100)      # cash 90,000, 100 shares
    p.update_equity_curve({"AAPL": 100.0}) # equity 100k -> peak
    p.update_equity_curve({"AAPL": 90.0})  # equity 99k -> dd 1k
    assert p.peak_equity == 100_000.0
    assert round(p.max_drawdown, 2) == 1_000.0


def test_stats_win_rate_and_profit_factor():
    p = Portfolio(balance=100_000.0)
    # 2 winners (+100 each), 1 loser (-50)
    p.execute_buy("A", 100.0, 1); p.execute_sell("A", 200.0, 1)
    p.execute_buy("B", 100.0, 1); p.execute_sell("B", 200.0, 1)
    p.execute_buy("C", 100.0, 1); p.execute_sell("C", 50.0, 1)
    s = p.stats()
    assert s["total_trades"] == 3
    assert s["wins"] == 2
    assert s["losses"] == 1
    assert round(s["win_rate"], 1) == 66.7
    # gross profit 200, gross loss 50 -> PF 4.0
    assert s["profit_factor"] == 4.0


def test_reset_daily():
    p = Portfolio(balance=100_000.0)
    p.execute_buy("A", 100.0, 1); p.execute_sell("A", 150.0, 1)
    assert p.daily_pnl == 50.0
    p.reset_daily()
    assert p.daily_pnl == 0.0
    assert p.daily_start_balance == p.balance
