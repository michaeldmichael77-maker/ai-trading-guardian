"""Pytest configuration.

Redirect persistence to a throwaway temp database BEFORE any test imports
``trading_bot.api`` (which instantiates Storage at module load). This guarantees
the test suite never reads or writes the real production database.
"""

import os
import tempfile

# Set the override as early as possible (import time of the test session).
_tmp_db = os.path.join(tempfile.gettempdir(), "guardian_test.db")
os.environ.setdefault("GUARDIAN_DB", _tmp_db)
