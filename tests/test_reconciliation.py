"""Money-handling reconciliation invariants.

These are property-style tests that lock down the P&L engine permanently: no
matter what the strategy does (longs, shorts, stops, trails), the accounting
identities must always hold. A failure here means real money would be
mis-counted, so these are the most important safety tests in the suite.
"""

from trading_bot import config
from trading_bot.backtest import Backtester
from trading_bot.engine.portfolio import Portfolio


EPS = 1e-6   # generous vs. the ~1e-11 float drift we actually observe


def _recon_equity(portfolio, prices):
    """equity must equal cash + mark-to-market of every open position."""
    return portfolio.balance + sum(
        pos["size"] * prices[s]
        for s, pos in portfolio.open_positions().items()
    )


def test_equity_identity_holds_every_tick():
    """equity == cash + Sum(size * price) on every tick of a full run."""
    bt = Backtester(seed=42)
    worst = 0.0
    for _ in range(600):
        prices = {}
        for sym in bt.symbols:
            p = bt.market.get_price(sym)
            prices[sym] = p
            bt.buffers[sym].append(p)
            if len(bt.buffers[sym]) > 200:
                bt.buffers[sym].pop(0)
            bt.sentiment.update(sym)
            bt._step_symbol(sym, p)
        eq = bt.portfolio.equity(prices)
        worst = max(worst, abs(eq - _recon_equity(bt.portfolio, prices)))
    assert worst < EPS


def test_realised_plus_unrealised_equals_total_pnl():
    """Sum(closed pnl) + unrealised == equity - starting balance."""
    bt = Backtester(seed=7)
    report = bt.run(ticks=600)
    prices = bt.market.snapshot()

    realised = sum(t["pnl"] for t in bt.portfolio.closed_trades)
    unrealised = bt.portfolio.unrealised_pnl(prices)
    equity = bt.portfolio.equity(prices)

    # Equity change == realised + unrealised - costs paid. (Commissions leave
    # cash but are not part of trade P&L, so they must be added back here.)
    total_pnl = equity - config.INITIAL_BALANCE
    assert abs((realised + unrealised - bt.total_costs) - total_pnl) < EPS
    # sanity: report's final equity matches the curve (report rounds to 2 dp)
    assert abs(report["final_equity"] - bt.equity_curve[-1]) < 0.01


def test_daily_pnl_tracks_realised_only():
    """Portfolio.daily_pnl accumulates realised P&L from every close."""
    p = Portfolio(balance=100_000.0)
    p.execute_buy("AAPL", 100.0, 10)
    p.execute_sell("AAPL", 110.0, 10)      # +100 realised
    p.execute_short("TSLA", 200.0, 5)
    p.execute_cover("TSLA", 180.0, 5)      # +100 realised
    assert abs(p.daily_pnl - 200.0) < EPS


def test_round_trip_long_is_cash_neutral_minus_pnl():
    """Open then immediately close at same price -> cash unchanged."""
    p = Portfolio(balance=100_000.0)
    p.execute_buy("AAPL", 100.0, 10)
    p.execute_sell("AAPL", 100.0, 10)
    assert abs(p.balance - 100_000.0) < EPS


def test_round_trip_short_is_cash_neutral_minus_pnl():
    p = Portfolio(balance=100_000.0)
    p.execute_short("AAPL", 100.0, 10)
    p.execute_cover("AAPL", 100.0, 10)
    assert abs(p.balance - 100_000.0) < EPS
