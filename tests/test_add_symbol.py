"""Tests for adding/removing your own watchlist symbols at runtime."""

import importlib

import pytest

from trading_bot import config
from trading_bot.engine.market import MarketSimulator


def test_market_add_symbol():
    m = MarketSimulator(seed=1)
    assert "/MGC" not in m.prices
    ok = m.add_symbol("/MGC", 2350.0)
    assert ok is True
    # It now returns a live price.
    p = m.get_price("/MGC")
    assert p is not None and p > 0


def test_market_add_symbol_duplicate():
    m = MarketSimulator(seed=1)
    m.add_symbol("/ZC", 440.0)
    assert m.add_symbol("/ZC", 440.0) is False


def test_known_symbols_have_prices():
    known = config.KNOWN_SYMBOLS
    for sym in ("/MGC", "/ZC", "/HE", "/MCL", "/GC", "/CL"):
        assert sym in known
        price, vol = known[sym]
        assert price > 0 and 0 < vol < 0.05


@pytest.fixture
def api_mod():
    """Fresh import of the api module so global SYMBOLS edits don't leak."""
    import trading_bot.api as api
    importlib.reload(api)
    yield api


def test_api_add_and_remove_symbol_roundtrip(api_mod):
    api = api_mod
    before = list(config.SYMBOLS)
    # add
    sym = "/ZW"
    if sym in config.SYMBOLS:
        config.SYMBOLS.remove(sym)
    config.SYMBOLS.append(sym)
    config.SEED_PRICES[sym] = 560.0
    config.SYMBOL_VOL[sym] = 0.002
    api.market.add_symbol(sym, 560.0)
    assert sym in config.SYMBOLS
    # remove
    config.SYMBOLS.remove(sym)
    assert sym not in config.SYMBOLS
    # restore original list for other tests
    config.SYMBOLS[:] = before
