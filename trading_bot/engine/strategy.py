"""AI strategy ensemble.

This module hosts several independent technical "voters". Each returns a
(signal, reason, confidence) tuple. The Hive-Mind blends their votes.
"""

import math
import pandas as pd
import pandas_ta as ta

# ---------------------------------------------------------------------------
# Indicator helpers
# ---------------------------------------------------------------------------
def sma(values, period):
    if len(values) < period: return None
    return sum(values[-period:]) / period

def ema(values, period):
    if len(values) < period: return None
    k = 2 / (period + 1)
    e = values[-period]
    for v in values[-period + 1:]:
        e = v * k + e * (1 - k)
    return e

def rsi(values, period=14):
    if len(values) < period + 1: return 50.0
    gains, losses = 0.0, 0.0
    for i in range(-period, 0):
        change = values[i] - values[i - 1]
        if change >= 0: gains += change
        else: losses -= change
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0: return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def macd(values, fast=12, slow=26, signal=9):
    if len(values) < slow + signal: return 0.0, 0.0
    fast_e = ema(values, fast)
    slow_e = ema(values, slow)
    if fast_e is None or slow_e is None: return 0.0, 0.0
    macd_line = fast_e - slow_e
    return macd_line, macd_line * 0.8

def bollinger(values, period=20, mult=2.0):
    if len(values) < period: return None, None, None
    window = values[-period:]
    mid = sum(window) / period
    var = sum((v - mid) ** 2 for v in window) / period
    sd = math.sqrt(var)
    return mid - mult * sd, mid, mid + mult * sd

# ---------------------------------------------------------------------------
# Individual voters (Restored for Hive-Mind compatibility)
# ---------------------------------------------------------------------------
class MovingAverageVoter:
    name = "MA_Cross"
    def vote(self, prices):
        short = sma(prices, 10)
        long = sma(prices, 30)
        if short is None or long is None: return "HOLD", "MA: warming up", 0.5
        price = prices[-1]
        spread = abs(short - long) / long if long else 0
        conf = min(0.9, 0.55 + spread * 40)
        if short > long and price > long: return "BUY", "MA: short>long", conf
        if short < long and price < long: return "SELL", "MA: short<long", conf
        return "HOLD", "MA: no cross", 0.5

class RSIVoter:
    name = "RSI"
    def vote(self, prices):
        r = rsi(prices, 14)
        if r <= 30: return "BUY", f"RSI oversold ({r:.0f})", min(0.9, 0.6 + (30 - r) / 50)
        if r >= 70: return "SELL", f"RSI overbought ({r:.0f})", min(0.9, 0.6 + (r - 70) / 50)
        return "HOLD", f"RSI neutral ({r:.0f})", 0.5

class MACDVoter:
    name = "MACD"
    def vote(self, prices):
        line, sig = macd(prices)
        if line > sig and line > 0: return "BUY", "MACD bullish", 0.65
        if line < sig and line < 0: return "SELL", "MACD bearish", 0.65
        return "HOLD", "MACD flat", 0.5

class BollingerVoter:
    name = "Bollinger"
    def vote(self, prices):
        lower, mid, upper = bollinger(prices)
        if lower is None: return "HOLD", "BB: warming up", 0.5
        price = prices[-1]
        if price <= lower: return "BUY", "BB: lower band", 0.7
        if price >= upper: return "SELL", "BB: upper band", 0.7
        return "HOLD", "BB: inside bands", 0.5

class MomentumVoter:
    name = "Momentum"
    def vote(self, prices):
        if len(prices) < 12: return "HOLD", "MOM: warming up", 0.5
        mom = (prices[-1] - prices[-12]) / prices[-12] if prices[-12] else 0
        if mom > 0.003: return "BUY", f"MOM +{mom*100:.2f}%", min(0.85, 0.55 + mom * 30)
        if mom < -0.003: return "SELL", f"MOM {mom*100:.2f}%", min(0.85, 0.55 + abs(mom) * 30)
        return "HOLD", "MOM flat", 0.5

# ---------------------------------------------------------------------------
# Blended strategy
# ---------------------------------------------------------------------------
class AIStrategy:
    def __init__(self, window_size=30):
        self.window_size = window_size
        self.voters = [
            MovingAverageVoter(),
            RSIVoter(),
            MACDVoter(),
            BollingerVoter(),
            MomentumVoter(),
        ]

    def analyze(self, price_history):
        if len(price_history) < self.window_size:
            return "HOLD", "Collecting data...", 0.5
        votes = [v.vote(price_history) for v in self.voters]
        buy = [c for s, _, c in votes if s == "BUY"]
        sell = [c for s, _, c in votes if s == "SELL"]
        if len(buy) > len(sell) and buy:
            conf = sum(buy) / len(buy) * (len(buy) / len(self.voters) + 0.5)
            return "BUY", f"{len(buy)}/{len(self.voters)} voters bullish", min(0.95, conf)
        if len(sell) > len(buy) and sell:
            conf = sum(sell) / len(sell) * (len(sell) / len(self.voters) + 0.5)
            return "SELL", f"{len(sell)}/{len(self.voters)} voters bearish", min(0.95, conf)
        return "HOLD", "Voters split / neutral", 0.5
