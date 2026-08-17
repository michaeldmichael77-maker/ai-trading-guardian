#!/bin/bash
# ============================================================
#  AI Trading Guardian — double-click launcher (Mac/Linux)
#  Just double-click this file. It does everything for you.
# ============================================================

# Always run from the folder this file lives in.
cd "$(dirname "$0")"

echo "============================================================"
echo "   AI TRADING GUARDIAN — starting up..."
echo "============================================================"
echo ""

# 1) Find Python 3.
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "❌ Python 3 is not installed."
    echo "   Please install it from https://www.python.org/downloads/ and try again."
    echo ""
    read -p "Press Enter to close..."
    exit 1
fi
echo "✅ Found Python: $($PY --version)"

# 2) Install the required packages (quietly; only if missing).
echo "📦 Checking/installing required packages (first run may take a minute)..."
$PY -m pip install --user --quiet -r requirements.txt 2>/dev/null

# 3) Open the browser automatically after a short delay.
( sleep 4
  URL="http://localhost:8000"
  if command -v open >/dev/null 2>&1; then open "$URL"            # macOS
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"  # Linux
  fi
) &

# 4) Start the app.
echo ""
echo "🚀 Starting the dashboard..."
echo "   Your browser will open automatically at:  http://localhost:8000"
echo ""
echo "   >>> To STOP the system completely: close this window, or press Ctrl+C <<<"
echo "============================================================"
echo ""
PYTHONPATH=. $PY trading_bot/main.py

echo ""
echo "AI Trading Guardian has stopped."
read -p "Press Enter to close..."
