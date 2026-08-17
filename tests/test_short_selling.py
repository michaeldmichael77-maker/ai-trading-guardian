"""Tests for short-selling support in the portfolio."""

from trading_bot.engine.portfolio import Portfolio


def test_open_short_records_negative_size():
    p = Portfolio(balance=100_000.0)
    p.execute_short("AAPL", 100.0, 10)
    pos = p.get_position("AAPL")
    assert pos["size"] == -10
    assert pos["side"] == "SHORT"
    # received proceeds up front
    assert p.balance == 100_000.0 + 1_000.0
    assert p.position_count() == 1


def test_short_profit_when_price_falls():
    p = Portfolio(balance=100_000.0)
    p.execute_short("AAPL", 100.0, 10)
    # unrealised: (100-90)*10 = +100
    assert p.unrealised_pnl({"AAPL": 90.0}) == 100.0


def test_short_loss_when_price_rises():
    p = Portfolio(balance=100_000.0)
    p.execute_short("AAPL", 100.0, 10)
    assert p.unrealised_pnl({"AAPL": 110.0}) == -100.0


def test_cover_realises_profit_and_closes():
    p = Portfolio(balance=100_000.0)
    p.execute_short("AAPL", 100.0, 10)        # balance 101,000
    result = p.execute_cover("AAPL", 90.0, 10)
    assert result["pnl"] == 100.0
    assert p.daily_pnl == 100.0
    assert p.position_count() == 0
    # balance: 100k +1000 (short) -900 (cover) = 100,100
    assert p.balance == 100_100.0


def test_partial_cover_keeps_remaining_short():
    p = Portfolio(balance=100_000.0)
    p.execute_short("AAPL", 100.0, 10)
    p.execute_cover("AAPL", 95.0, 4)
    pos = p.get_position("AAPL")
    assert pos["size"] == -6
    assert pos["side"] == "SHORT"


def test_adding_to_short_averages_price():
    p = Portfolio(balance=100_000.0)
    p.execute_short("AAPL", 100.0, 10)
    p.execute_short("AAPL", 120.0, 10)
    pos = p.get_position("AAPL")
    assert pos["size"] == -20
    assert pos["avg_price"] == 110.0


def test_cannot_short_while_long():
    p = Portfolio(balance=100_000.0)
    p.execute_buy("AAPL", 100.0, 10)
    assert p.execute_short("AAPL", 100.0, 5) is None


def test_cannot_cover_when_flat_or_long():
    p = Portfolio(balance=100_000.0)
    assert p.execute_cover("AAPL", 100.0, 5) is None
    p.execute_buy("AAPL", 100.0, 10)
    assert p.execute_cover("AAPL", 100.0, 5) is None


def test_equity_correct_with_short():
    p = Portfolio(balance=100_000.0)
    p.execute_short("AAPL", 100.0, 10)        # balance 101,000, size -10
    # equity = cash + size*price = 101,000 + (-10*90) = 101,000 - 900 = 100,100
    assert p.equity({"AAPL": 90.0}) == 100_100.0


def test_short_appears_in_stats_after_cover():
    p = Portfolio(balance=100_000.0)
    p.execute_short("A", 100.0, 1)
    p.execute_cover("A", 80.0, 1)             # +20 winner
    s = p.stats()
    assert s["total_trades"] == 1
    assert s["wins"] == 1
