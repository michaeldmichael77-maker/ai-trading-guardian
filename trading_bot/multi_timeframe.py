"""Multi-timeframe confirmation.

A signal is only "aligned" when the short, medium and long timeframe trends
agree.  We derive pseudo-timeframes by resampling the tick buffer into bars of
increasing size (fast/mid/slow) and comparing their moving-average slopes.
"""


class MultiTimeframeConfirmation:
    def __init__(self, fast=5, mid=15, slow=30):
        self.fast = fast
        self.mid = mid
        self.slow = slow

    @staticmethod
    def _direction(window):
        if len(window) < 2:
            return 0
        first_half = window[: len(window) // 2]
        second_half = window[len(window) // 2:]
        a = sum(first_half) / len(first_half)
        b = sum(second_half) / len(second_half)
        if b > a * 1.0002:
            return 1
        if b < a * 0.9998:
            return -1
        return 0

    def check_alignment(self, price_history):
        if len(price_history) < self.slow:
            return {"aligned": False, "direction": "NONE", "timeframes": {}}

        fast_dir = self._direction(price_history[-self.fast:])
        mid_dir = self._direction(price_history[-self.mid:])
        slow_dir = self._direction(price_history[-self.slow:])

        timeframes = {"fast": fast_dir, "mid": mid_dir, "slow": slow_dir}

        aligned_up = fast_dir == mid_dir == slow_dir == 1
        aligned_down = fast_dir == mid_dir == slow_dir == -1
        aligned = aligned_up or aligned_down

        direction = "UP" if aligned_up else "DOWN" if aligned_down else "MIXED"
        return {
            "aligned": aligned,
            "direction": direction,
            "timeframes": timeframes,
        }
