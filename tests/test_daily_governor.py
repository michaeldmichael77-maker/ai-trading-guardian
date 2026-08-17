"""Tests for the Daily Governor - the safety-critical limit enforcer."""

from trading_bot.daily_governor import DailyGovernor, DailyLimits


def make_gov():
    return DailyGovernor(DailyLimits(max_profit=7000.0, max_loss=175.0,
                                     per_trade_stop_loss=50.0))


def test_start_new_day():
    g = make_gov()
    assert g.start_new_day(100_000.0) is True
    assert g.active is True
    assert g.day_start_balance == 100_000.0
    assert g.should_continue_trading() is True


def test_cannot_start_twice():
    g = make_gov()
    g.start_new_day(100_000.0)
    assert g.start_new_day(100_000.0) is False


def test_profit_target_ends_day():
    g = make_gov()
    g.start_new_day(100_000.0)
    g.update_pnl(107_000.0)                 # +7,000
    assert g.should_continue_trading() is False
    assert "profit target" in g.get_shutdown_reason().lower()


def test_just_below_profit_target_keeps_trading():
    g = make_gov()
    g.start_new_day(100_000.0)
    g.update_pnl(106_999.0)                 # +6,999
    assert g.should_continue_trading() is True


def test_loss_limit_ends_day():
    g = make_gov()
    g.start_new_day(100_000.0)
    g.update_pnl(100_000.0 - 175.0)         # -175
    assert g.should_continue_trading() is False
    assert "loss limit" in g.get_shutdown_reason().lower()


def test_just_above_loss_limit_keeps_trading():
    # With the 0.90 safety buffer, the halt trigger for a $175 limit is $157.50.
    # A loss under that threshold must keep trading.
    g = make_gov()
    g.start_new_day(100_000.0)
    g.update_pnl(100_000.0 - 150.0)         # -150 < 157.50 trigger
    assert g.should_continue_trading() is True


def test_safety_buffer_halts_before_absolute_limit():
    g = make_gov()
    g.start_new_day(100_000.0)
    g.update_pnl(100_000.0 - 160.0)         # past 0.90*175 = 157.50
    assert g.should_continue_trading() is False


def test_register_and_close_position():
    g = make_gov()
    g.start_new_day(100_000.0)
    g.register_position("AAPL", 100.0, 5, "BUY")
    assert g.trades_today == 1
    assert "AAPL" in g.positions
    g.close_position("AAPL")
    assert "AAPL" not in g.positions


def test_end_day_sets_reason():
    g = make_gov()
    g.start_new_day(100_000.0)
    g.end_day("Manual end")
    assert g.active is False
    assert g.get_shutdown_reason() == "Manual end"


def test_summary_progress_fields():
    g = make_gov()
    g.start_new_day(100_000.0)
    g.update_pnl(103_500.0)                 # +3,500 = 50% of 7,000
    s = g.summary()
    assert s["profit_progress"] == 50.0
    assert s["loss_progress"] == 0.0
    assert s["daily_pnl"] == 3500.0
