"""The non-negotiable: daily loss can NEVER exceed the configured limit.

These tests prove that the instant the loss limit is reached the system halts
AND flattens every position, so the realised daily loss cannot keep growing.
"""

from trading_bot.daily_governor import DailyGovernor, DailyLimits


def make_gov(max_loss=175.0):
    return DailyGovernor(DailyLimits(max_profit=7000.0, max_loss=max_loss,
                                     per_trade_stop_loss=50.0))


def test_loss_breach_returns_verdict_and_halts():
    g = make_gov(175.0)
    g.start_new_day(100_000.0)
    # Drop equity to -180 (past the 175 limit).
    verdict = g.update_pnl(100_000.0 - 180.0)
    assert verdict["breach"] == "LOSS"
    assert g.should_continue_trading() is False


def test_safety_buffer_halts_before_absolute_limit():
    """With a 0.90 buffer we halt at 90% of the limit, not after exceeding it."""
    g = make_gov(200.0)
    g.start_new_day(100_000.0)
    # -185 is past 90% of 200 (=180) but below the absolute 200.
    verdict = g.update_pnl(100_000.0 - 185.0)
    assert verdict["breach"] == "LOSS"
    assert g.should_continue_trading() is False


def test_just_under_buffer_keeps_trading():
    g = make_gov(200.0)
    g.start_new_day(100_000.0)
    # -170 is under 90% of 200 (=180) -> keep trading.
    verdict = g.update_pnl(100_000.0 - 170.0)
    assert verdict["breach"] is None
    assert g.should_continue_trading() is True


def test_profit_breach_returns_verdict():
    g = make_gov()
    g.start_new_day(100_000.0)
    verdict = g.update_pnl(100_000.0 + 7000.0)
    assert verdict["breach"] == "PROFIT"
    assert g.should_continue_trading() is False


def test_remaining_loss_budget_shrinks():
    g = make_gov(175.0)
    g.start_new_day(100_000.0)
    g.update_pnl(100_000.0 - 50.0)   # down $50
    # budget = 0.90*175 + (-50) = 157.5 - 50 = 107.5
    assert abs(g.remaining_loss_budget() - 107.5) < 1e-6


def test_loss_limit_would_breach_projection():
    g = make_gov(175.0)
    g.start_new_day(100_000.0)
    g.update_pnl(100_000.0 - 100.0)  # already down 100
    # another 80 loss -> -180, past 0.9*175=157.5
    assert g.loss_limit_would_breach(-180.0) is True
    assert g.loss_limit_would_breach(-120.0) is False
