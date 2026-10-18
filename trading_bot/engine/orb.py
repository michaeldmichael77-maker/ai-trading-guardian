"""Institutional 15-Minute Opening Range Breakout (ORB) Engine.

Designed specifically for CME Futures (Micro Nasdaq /MNQ and Micro S&P /MES).
Locks in the 9:30 AM - 9:45 AM EST range and trades the high-volume morning
momentum wave between 9:45 AM and 11:30 AM EST, completely eliminating
afternoon chop and commission fee-bleed.
"""

from datetime import datetime
import time
import zoneinfo

NY_TZ = zoneinfo.ZoneInfo("America/New_York")


class OpeningRangeBreakout:
    """Manages the daily 15-minute Opening Range on CME Futures."""

    def __init__(self, target_symbol="/NQ", range_start_m=30, range_end_m=45, cutoff_hour=11, cutoff_minute=30):
        self.symbol = target_symbol
        self.range_start_m = range_start_m  # 9:30 AM
        self.range_end_m = range_end_m      # 9:45 AM
        self.cutoff_hour = cutoff_hour      # 11:30 AM
        self.cutoff_minute = cutoff_minute

        self.current_date = None
        self.orb_high = None
        self.orb_low = None
        self.range_locked = False
        self.trades_taken_today = 0
        self.max_trades_per_day = 2

    def reset_if_new_day(self, now_dt):
        today_str = now_dt.strftime("%Y-%m-%d")
        if self.current_date != today_str:
            self.current_date = today_str
            self.orb_high = None
            self.orb_low = None
            self.range_locked = False
            self.trades_taken_today = 0

    def evaluate(self, current_price: float, high_price: float = None, low_price: float = None, now_ts: float = None):
        """Evaluate ORB status on every tick/minute bar.

        Returns dict with:
            signal: "BUY" | "SELL" | "HOLD" | "FLATTEN"
            confidence: float (0.0 to 1.0)
            reason: str
            orb_high: float
            orb_low: float
            is_active_window: bool
        """
        now_dt = datetime.fromtimestamp(now_ts or time.time(), tz=NY_TZ)
        self.reset_if_new_day(now_dt)

        h = now_dt.hour
        m = now_dt.minute

        high = high_price or current_price
        low = low_price or current_price

        # 1. Before 9:30 AM EST: Pre-market -> HOLD
        if h < 9 or (h == 9 and m < self.range_start_m):
            return {
                "signal": "HOLD",
                "confidence": 0.5,
                "reason": f"Pre-market wait (Opens 9:30 AM EST) | Now {now_dt.strftime('%H:%M:%S')}",
                "orb_high": self.orb_high,
                "orb_low": self.orb_low,
                "is_active_window": False,
            }

        # 2. 9:30 AM - 9:45 AM EST: Range Building Window
        if h == 9 and self.range_start_m <= m < self.range_end_m:
            if self.orb_high is None or high > self.orb_high:
                self.orb_high = high
            if self.orb_low is None or low < self.orb_low:
                self.orb_low = low
            return {
                "signal": "HOLD",
                "confidence": 0.5,
                "reason": f"Building 15m Opening Range (9:30-9:45) | High: {self.orb_high} Low: {self.orb_low}",
                "orb_high": self.orb_high,
                "orb_low": self.orb_low,
                "is_active_window": False,
            }

        # Lock the range once 9:45 AM is reached
        if not self.range_locked and self.orb_high is not None and self.orb_low is not None:
            self.range_locked = True

        # 3. 9:45 AM - 11:30 AM EST: Institutional Breakout Window
        in_trade_window = (h == 9 and m >= self.range_end_m) or (h == 10) or (h == 11 and m < self.cutoff_minute)
        if in_trade_window:
            if not self.range_locked or self.orb_high is None:
                return {"signal": "HOLD", "confidence": 0.5, "reason": "ORB range unformed", "is_active_window": True}

            if self.trades_taken_today >= self.max_trades_per_day:
                return {
                    "signal": "HOLD",
                    "confidence": 0.5,
                    "reason": f"Max daily trades reached ({self.trades_taken_today}/{self.max_trades_per_day}) — protecting capital",
                    "orb_high": self.orb_high,
                    "orb_low": self.orb_low,
                    "is_active_window": True,
                }

            # Breakout Above High -> Strong Institutional BUY
            if current_price > self.orb_high:
                return {
                    "signal": "BUY",
                    "confidence": 0.88,
                    "reason": f"15m ORB High Breakout ({current_price:.2f} > {self.orb_high:.2f})",
                    "orb_high": self.orb_high,
                    "orb_low": self.orb_low,
                    "is_active_window": True,
                }

            # Breakdown Below Low -> Strong Institutional SHORT
            if current_price < self.orb_low:
                return {
                    "signal": "SELL",
                    "confidence": 0.88,
                    "reason": f"15m ORB Low Breakdown ({current_price:.2f} < {self.orb_low:.2f})",
                    "orb_high": self.orb_high,
                    "orb_low": self.orb_low,
                    "is_active_window": True,
                }

            return {
                "signal": "HOLD",
                "confidence": 0.5,
                "reason": f"Inside 15m Range ({self.orb_low:.2f} - {self.orb_high:.2f}) | Awaiting breakout",
                "orb_high": self.orb_high,
                "orb_low": self.orb_low,
                "is_active_window": True,
            }

        # 4. Past 11:30 AM EST: Hard Cutoff -> No afternoon chop!
        return {
            "signal": "FLATTEN",
            "confidence": 0.95,
            "reason": "11:30 AM EST Cutoff reached — session closed to avoid afternoon chop",
            "orb_high": self.orb_high,
            "orb_low": self.orb_low,
            "is_active_window": False,
        }

    def record_trade(self):
        self.trades_taken_today += 1
