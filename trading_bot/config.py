# --- DEFAULT RISK PROFILES ---
RISK_PROFILES = {
    "CONSERVATIVE": {
        "daily_profit_limit": 500.0,
        "daily_loss_limit": 50.0,
        "trailing_stop": 20.0,
        "description": "Focus on capital preservation. Tight stops."
    },
    "BALANCED": {
        "daily_profit_limit": 3500.0,
        "daily_loss_limit": 75.0,
        "trailing_stop": 50.0,
        "description": "Balanced growth and risk."
    },
    "AGGRESSIVE": {
        "daily_profit_limit": 10000.0,
        "daily_loss_limit": 500.0,
        "trailing_stop": 150.0,
        "description": "High risk for higher reward. Wider stops."
    }
}

# --- INSTITUTIONAL ENGINE SETTINGS ---
MAX_DAILY_PROFIT = 7000.0
MAX_DAILY_LOSS = 75.0
PER_TRADE_STOP_LOSS = 50.0
MAX_PORTFOLIO_HEAT = 0.05
MAX_POSITION_PCT = 0.25
MAX_GROSS_LEVERAGE = 1.0
RISK_PER_TRADE_PCT = 0.01
STOP_ATR_MULT = 3.0

# Exit targets (R-multiples)
TAKE_PROFIT_R = 2.0
TRAIL_ACTIVATE_R = 1.5
TRAIL_GIVEBACK = 0.25

# --- TRADING TARGETS ---
SYMBOLS = ["BTC/USD", "ETH/USD", "NVDA", "TSLA", "AAPL", "QQQ", "SPY", "TLT", "/ES", "/CL"]
SEED_PRICES = {"BTC/USD": 72000.0, "ETH/USD": 3500.0, "NVDA": 120.0, "TSLA": 230.0, "AAPL": 198.0, "QQQ": 495.0, "SPY": 540.0, "TLT": 106.0, "/ES": 5400.0, "/CL": 76.0}
SYMBOL_VOL = {s: 0.0015 for s in SYMBOLS}

# --- SYSTEM PARAMETERS ---
INITIAL_BALANCE = 100000.00
TICK_INTERVAL = 2
WARMUP_TICKS = 30
TRADING_MODE = "sim"
USE_VOL_SIZING = True
VOL_WINDOW = 20
MIN_CONFIDENCE = 0.6

# --- ALLOCATOR SETTINGS ---
ALLOCATOR_DATA_DIR = "data_focus"
ALLOCATOR_TREND_WINDOW = 200
ALLOCATOR_VOL_WINDOW = 20
ALLOCATOR_REBALANCE_EVERY = 5
ALLOCATOR_CRASH_FILTER = True
ALLOCATOR_MARKET = "SPY"
ALLOCATOR_MAX_WEIGHT = 0.4
