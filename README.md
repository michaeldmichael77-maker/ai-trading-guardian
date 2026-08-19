# AI Trading Guardian

An autonomous, AI-powered paper trading platform with real-time risk management. Built to run 24/7, enforce strict profit/loss rules, and remove emotional decision-making from trading.

## Two Versions Included

This project contains **two independent applications**:

### 1. Standalone HTML App (`AI_Trading_Guardian.html`)
**Zero installation. Double-click and run.**
- Opens in any modern browser (Chrome, Edge, Firefox, Safari)
- Works offline with a built-in market simulator
- Optional live crypto data via Binance public stream (no API key needed)
- All AI logic (RSI, MACD, EMA, Bollinger Bands) runs in JavaScript
- Portfolio, trade history, and settings persist via localStorage
- **Best for:** Quick testing, demoing, or users who don't want to install Python

### 2. Python Backend + Dashboard (`trading_bot/`)
**Professional server-based stack.**
- FastAPI backend with background trading loop
- Alpaca API integration for real stock market paper trading
- Real-time web dashboard at `localhost:8000`
- Modular engine architecture (Market, Portfolio, Guardian, Strategy)
- **Best for:** Real stock trading, server deployment, advanced customization

---

## Standalone HTML App — Quick Start

1. Download `AI_Trading_Guardian.html`
2. Double-click the file (or drag it into any browser)
3. Press **"START SYSTEM"**
4. The AI begins watching simulated prices immediately

**Switch to Live Crypto Data:**
- Click **"Toggle Simulator / Live Crypto"**
- Connects to Binance's free public WebSocket stream (BTC/USDT)
- No account or API key required

---

## Python Backend — Quick Start

### Prerequisites
- Python 3.9+
- pip

### Installation
```bash
# Extract the project first (if using rebuild_project.py)
python rebuild_project.py

# Install dependencies
cd trading_bot
pip install -r requirements.txt
```

### Launch
```bash
python main.py
```

Open your browser to: **http://localhost:8000/static/index.html**

### Connect Real Stock Market Data (Optional)
1. Sign up for free at [Alpaca.markets](https://alpaca.markets)
2. Get your **Paper Trading** API keys (not live trading)
3. Paste them into the **API Connection** panel on the dashboard
4. Click **"Connect to Real Market"**

---

## Core Features

| Feature | Description |
|---|---|
| **Autonomous Trading** | AI executes buy/sell signals automatically based on technical indicators |
| **Manual Co-Pilot Mode** | AI suggests trades; you press the button to execute |
| **Guardian Risk Engine** | Enforces daily profit caps, daily loss floors, and trailing stops |
| **Kill Switch** | Instantly halts all trading when a risk limit is breached |
| **Trailing Stop** | Locks in profits by selling if price drops $X from its peak |
| **Risk Profiles** | One-click switching between Conservative, Balanced, and Aggressive presets |
| **Trade History** | Persistent log of every trade with PnL and reasoning |
| **Real-Time Chart** | Canvas-rendered live price chart with gradient fill |
| **Live Market Data** | Simulator mode (offline) OR real Binance crypto stream OR Alpaca stock API |

---

## AI Strategy Logic

The brain uses a **multi-indicator convergence strategy**:

1. **RSI (14-period)** — Detects oversold (< 35) and overbought (> 65) conditions
2. **EMA (20-period)** — Confirms trend direction
3. **MACD (12/26)** — Validates momentum before entering
4. **Bollinger Bands (20, 2σ)** — Identifies extreme price ranges

**BUY Signal:** RSI oversold OR price at lower Bollinger Band + price above EMA + MACD bullish
**SELL Signal:** RSI overbought OR price at upper Bollinger Band OR MACD bearish + price below EMA

---

## File Structure

```
AI_Trading_Guardian.html   <-- Standalone browser app (no install needed)
rebuild_project.py          <-- One-click rebuild script for the Python project
README.md                   <-- This file

trading_bot/
├── main.py                 # Entry point (launches uvicorn server)
├── api.py                  # FastAPI routes + background bot loop
├── config.py               # Risk profiles and default constants
├── requirements.txt        # Python dependencies
├── engine/
│   ├── market.py           # MarketSimulator + AlpacaConnector
│   ├── portfolio.py        # Virtual wallet + trade history records
│   ├── guardian.py         # Risk management + kill switch logic
│   └── strategy.py         # AI brain (RSI/MACD/Bollinger analysis)
└── static/
    └── index.html          # Web dashboard (React-like JS interface)
```

---

## How to Continue in a New Chat

**Arena workspaces do NOT persist across conversations.** To continue editing this project in a new chat, upload these three files:

1. **`rebuild_project.py`** — Reconstructs the entire Python backend and dashboard
2. **`AI_Trading_Guardian.html`** — The standalone browser app (if you want to edit the no-install version)
3. **`README.md`** — This documentation (optional but helpful for context)

### Prompt to use in the new chat:
```
I am continuing my AI Trading Guardian project. Please read these three files:
- rebuild_project.py (rebuilds the Python backend)
- AI_Trading_Guardian.html (standalone browser app)
- README.md (project documentation)

Run "python rebuild_project.py" first to restore the full trading_bot/ directory.
Then confirm the file structure is intact and tell me what you'd like to work on next.
```

---

## Important Disclaimer

This software is for **educational and development purposes only**. It does not constitute financial advice. Automated trading carries substantial risk of loss. Always test thoroughly in paper/simulation mode before considering any real capital deployment. Past performance of any strategy does not guarantee future results.

---

## Roadmap / Potential Next Steps

- **Real Order Execution:** Submit actual paper orders through Alpaca's API instead of internal simulation
- **Backtesting Engine:** Feed historical data through the strategy to measure win rate and Sharpe ratio
- **Machine Learning Layer:** Replace indicator rules with trained models (Random Forest / LSTM)
- **Multi-Asset Screening:** Monitor and trade multiple symbols simultaneously
- **Database Persistence:** SQLite/PostgreSQL for permanent trade logging across server restarts
- **Mobile App Wrapper:** Package the HTML dashboard into a native iOS/Android app via Capacitor or Tauri

---

**Built for:** Everyday investors who want institutional-grade risk management without institutional complexity.

**License:** Personal / Educational Use
