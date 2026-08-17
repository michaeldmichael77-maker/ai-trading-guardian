"""Tests for the centralised exit manager (stop / take-profit / trailing)."""

from trading_bot.exit_manager import ExitManager


def long_pos(avg, size=10):
    return {"size": size, "avg_price": avg, "side": "LONG"}


def short_pos(avg, size=10):
    return {"size": size, "avg_price": avg, "side": "SHORT"}


# --------------------------------------------------------------------------- #
# Unrealised P&L
# --------------------------------------------------------------------------- #
def test_unrealised_long():
    em = ExitManager(per_trade_stop=50)
    assert em.unrealised(long_pos(100, 10), 105) == 50.0


def test_unrealised_short():
    em = ExitManager(per_trade_stop=50)
    # short from 100, price drops to 95 -> +50 profit
    assert em.unrealised(short_pos(100, 10), 95) == 50.0
    # short from 100, price rises to 105 -> -50 loss
    assert em.unrealised(short_pos(100, 10), 105) == -50.0


# --------------------------------------------------------------------------- #
# Hard stop
# --------------------------------------------------------------------------- #
def test_hard_stop_long():
    em = ExitManager(per_trade_stop=50, take_profit_r=2.0)
    pos = long_pos(100, 10)          # $10/point
    r = em.check("AAPL", pos, 94.9)  # -51 loss
    assert r["reason"] == "STOP-LOSS"


def test_hard_stop_short():
    em = ExitManager(per_trade_stop=50)
    pos = short_pos(100, 10)
    r = em.check("AAPL", pos, 105.1) # short loss of 51
    assert r["reason"] == "STOP-LOSS"


def test_no_exit_within_band():
    em = ExitManager(per_trade_stop=50, take_profit_r=2.0)
    assert em.check("AAPL", long_pos(100, 10), 102) is None  # +20, < TP, > stop


# --------------------------------------------------------------------------- #
# Take profit
# --------------------------------------------------------------------------- #
def test_take_profit_long():
    em = ExitManager(per_trade_stop=50, take_profit_r=2.0)
    pos = long_pos(100, 10)          # +100 = 2R at price 110
    r = em.check("AAPL", pos, 110)
    assert r["reason"] == "TAKE-PROFIT"


def test_take_profit_disabled_when_zero():
    em = ExitManager(per_trade_stop=50, take_profit_r=0)
    # +200 profit but TP disabled -> trailing or hold, never TAKE-PROFIT
    r = em.check("AAPL", long_pos(100, 10), 120)
    assert r is None or r["reason"] != "TAKE-PROFIT"


# --------------------------------------------------------------------------- #
# Trailing stop
# --------------------------------------------------------------------------- #
def test_trailing_stop_triggers_after_giveback():
    em = ExitManager(per_trade_stop=50, take_profit_r=5.0,
                     trail_activate_r=1.0, trail_giveback=0.5)
    pos = long_pos(100, 10)
    # climb to +80 (peak), arming the trail (>= 1R = 50)
    assert em.check("AAPL", pos, 108) is None
    assert em.peak("AAPL") == 80.0
    # give back to +30 (< 50% of 80 = 40) -> trail exit
    r = em.check("AAPL", pos, 103)
    assert r["reason"] == "TRAIL-STOP"


def test_trailing_not_armed_below_activation():
    em = ExitManager(per_trade_stop=50, take_profit_r=5.0,
                     trail_activate_r=1.0, trail_giveback=0.5)
    pos = long_pos(100, 10)
    em.check("AAPL", pos, 104)   # +40 peak, below 1R activation
    r = em.check("AAPL", pos, 100)  # back to 0, but trail never armed
    assert r is None


def test_peak_reset_on_open():
    em = ExitManager(per_trade_stop=50)
    pos = long_pos(100, 10)
    em.check("AAPL", pos, 108)
    assert em.peak("AAPL") == 80.0
    em.on_open("AAPL")
    assert em.peak("AAPL") == 0.0


def test_on_close_clears_state():
    em = ExitManager(per_trade_stop=50)
    em.check("AAPL", long_pos(100, 10), 108)
    em.on_close("AAPL")
    assert em.peak("AAPL") == 0.0


def test_precedence_stop_before_tp():
    # A position can't be both; ensure a losing position never returns TP.
    em = ExitManager(per_trade_stop=50, take_profit_r=2.0)
    r = em.check("AAPL", long_pos(100, 10), 94)  # -60 loss
    assert r["reason"] == "STOP-LOSS"
