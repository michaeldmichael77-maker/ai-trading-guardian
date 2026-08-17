"""News / economic-event filter.

In a live deployment this would subscribe to an economic calendar and a news
feed.  Here we simulate scheduled high-impact events (FOMC, CPI, earnings) that
create temporary "blackout" windows during which new entries are blocked to
avoid headline risk.
"""

import random
import time


class NewsEventFilter:
    def __init__(self, blackout_seconds=20):
        self._rng = random.Random()
        self.blackout_seconds = blackout_seconds
        self.active_event = None
        self.event_until = 0.0
        self._next_check = 0.0
        self.recent_events = []

    def _maybe_spawn_event(self):
        now = time.time()
        if now < self._next_check:
            return
        # Check for a new event roughly every 15s.
        self._next_check = now + 15
        # ~12% chance of a high-impact event window opening.
        if self._rng.random() < 0.12:
            event = self._rng.choice(
                ["FOMC Statement", "CPI Release", "NFP Jobs Report",
                 "Earnings Surprise", "Fed Speaker", "Geopolitical Headline"]
            )
            self.active_event = event
            self.event_until = now + self.blackout_seconds
            self.recent_events.insert(0, {"event": event, "time": now})
            self.recent_events = self.recent_events[:5]

    def is_blackout(self):
        self._maybe_spawn_event()
        now = time.time()
        if self.active_event and now < self.event_until:
            return True
        if self.active_event and now >= self.event_until:
            self.active_event = None
        return False

    def status(self):
        in_blackout = self.is_blackout()
        return {
            "blackout": in_blackout,
            "active_event": self.active_event if in_blackout else None,
            "seconds_remaining": (
                round(max(0.0, self.event_until - time.time()), 1)
                if in_blackout else 0.0
            ),
        }
