"""Tests for historical CSV replay (CSVMarket + Backtester integration)."""

import csv
import os

import pytest

from trading_bot.engine.csv_market import CSVMarket
from trading_bot.backtest import Backtester


@pytest.fixture
def csv_dir(tmp_path):
    """Write two tiny CSVs (one a futures symbol with a slash)."""
    def write(symbol, closes):
        safe = symbol.replace("/", "_")
        with open(tmp_path / f"{safe}.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["close"])
            for c in closes:
                w.writerow([c])

    write("AAPL", [100, 101, 102, 103, 104])
    write("/ES", [5000, 5010, 5020, 5030, 5040])
    return str(tmp_path)


def test_loads_symbols_including_slash(csv_dir):
    m = CSVMarket(csv_dir)
    assert set(m.symbols) == {"AAPL", "/ES"}
    assert m.length() == 5


def test_get_price_advances_in_order(csv_dir):
    m = CSVMarket(csv_dir)
    assert m.get_price("AAPL") == 100
    assert m.get_price("AAPL") == 101
    assert m.get_price("AAPL") == 102


def test_get_price_holds_last_after_end(csv_dir):
    m = CSVMarket(csv_dir)
    for _ in range(5):
        m.get_price("AAPL")
    # past the end -> repeats the final close
    assert m.get_price("AAPL") == 104
    assert m.get_price("AAPL") == 104


def test_snapshot_reflects_last_prices(csv_dir):
    m = CSVMarket(csv_dir)
    m.get_price("AAPL")
    m.get_price("/ES")
    snap = m.snapshot()
    assert snap["AAPL"] == 100
    assert snap["/ES"] == 5000


def test_case_insensitive_header(tmp_path):
    with open(tmp_path / "AAPL.csv", "w", newline="") as fh:
        fh.write("Date,Open,Close\n")
        fh.write("2020-01-01,99,100\n")
        fh.write("2020-01-02,100,101\n")
    m = CSVMarket(str(tmp_path))
    assert m.get_price("AAPL") == 100
    assert m.get_price("AAPL") == 101


def test_empty_dir_raises(tmp_path):
    with pytest.raises(ValueError):
        CSVMarket(str(tmp_path))


def test_symbol_filter(csv_dir):
    m = CSVMarket(csv_dir, symbols=["AAPL"])
    assert m.symbols == ["AAPL"]


def test_backtester_runs_on_csv_market(csv_dir):
    m = CSVMarket(csv_dir)
    bt = Backtester(market=m)
    report = bt.run(ticks=m.length())
    # With only 5 bars (< warmup) no trades fire, but it must run cleanly
    # and preserve the equity identity.
    assert "final_equity" in report
    assert bt.symbols == m.symbols


def test_backtester_trades_on_longer_csv(tmp_path):
    """A longer real-style series should pass warmup and produce trades."""
    from trading_bot.export_csv import export
    export(str(tmp_path), bars=400, seed=42)
    m = CSVMarket(str(tmp_path))
    bt = Backtester(market=m)
    report = bt.run(ticks=m.length())
    assert report["total_trades"] > 0
