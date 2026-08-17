"""Entry point.

Local:  PYTHONPATH=. python3 trading_bot/main.py   (uses port 8000)
Cloud:  Render sets the PORT environment variable automatically; we honor it.
"""

import os

import uvicorn

from trading_bot.api import app  # noqa: F401  (import registers routes)


def run():
    # Render (and most hosts) provide the port to bind via the PORT env var.
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "trading_bot.api:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    run()
