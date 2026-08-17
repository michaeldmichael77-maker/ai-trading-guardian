"""Tests for regime detection, multi-timeframe and the hive-mind."""

from trading_bot.regime_detector import RegimeDetector
from trading_bot.multi_timeframe import MultiTimeframeConfirmation
from trading_bot.hive_mind import HiveMind
from trading_bot.engine.strategy import AIStrategy, rsi, sma


def test_regime_unknown_when_insufficient_data():
    d = RegimeDetector()
    assert d.detect_regime([100.0] * 10) == "UNKNOWN"


def test_regime_trending_up():
    d = RegimeDetector()
    prices = [100.0 * (1.002 ** i) for i in range(40)]   # steady climb
    assert d.detect_regime(prices) == "TRENDING_UP"


def test_regime_trending_down():
    d = RegimeDetector()
    prices = [100.0 * (0.998 ** i) for i in range(40)]
    assert d.detect_regime(prices) == "TRENDING_DOWN"


def test_regime_ranging():
    d = RegimeDetector()
    prices = [100.0 + (0.05 if i % 2 else -0.05) for i in range(40)]
    assert d.detect_regime(prices) == "RANGING"


def test_regime_volatile():
    d = RegimeDetector()
    prices = [100.0 * (1.02 if i % 2 else 0.98) for i in range(40)]
    assert d.detect_regime(prices) == "VOLATILE"


def test_mtf_warming_up():
    m = MultiTimeframeConfirmation()
    r = m.check_alignment([100.0] * 10)
    assert r["aligned"] is False


def test_mtf_aligned_uptrend():
    m = MultiTimeframeConfirmation()
    prices = [100.0 * (1.003 ** i) for i in range(40)]
    r = m.check_alignment(prices)
    assert r["aligned"] is True
    assert r["direction"] == "UP"


# --------------------------------------------------------------------------- #
# Indicator sanity
# --------------------------------------------------------------------------- #
def test_sma_basic():
    assert sma([1, 2, 3, 4, 5], 5) == 3.0
    assert sma([1, 2], 5) is None


def test_rsi_all_gains_is_high():
    prices = list(range(1, 30))             # monotonically increasing
    assert rsi(prices, 14) == 100.0


def test_rsi_neutral_default_when_short():
    assert rsi([1, 2, 3], 14) == 50.0


# --------------------------------------------------------------------------- #
# Hive-Mind
# --------------------------------------------------------------------------- #
def test_hive_warming_up():
    h = HiveMind()
    d = h.decide([100.0] * 10)
    assert d["signal"] == "HOLD"


def test_hive_returns_valid_structure():
    h = HiveMind()
    prices = [100.0 * (1.002 ** i) for i in range(50)]
    d = h.decide(prices, regime="TRENDING_UP")
    assert d["signal"] in ("BUY", "SELL", "HOLD")
    assert 0.0 <= d["confidence"] <= 1.0
    assert len(d["votes"]) == 5


def test_hive_set_weights():
    h = HiveMind()
    h.set_weights({"RSI": 1.5})
    assert h.weights["RSI"] == 1.5


def test_aistrategy_contract_preserved():
    """The original AIStrategy().analyze() contract must still hold."""
    s = AIStrategy()
    signal, reason, conf = s.analyze([100.0] * 10)
    assert signal == "HOLD"
    assert isinstance(reason, str)
    assert isinstance(conf, float)
