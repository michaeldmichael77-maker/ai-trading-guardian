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

# --- ADVANCED ENGINE MAPPINGS ---
# Translation layer to support the Full Version engine modules
MAX_DAILY_PROFIT = RISK_PROFILES["BALANCED"]["daily_profit_limit"]
MAX_DAILY_LOSS = RISK_PROFILES["BALANCED"]["daily_loss_limit"]
PER_TRADE_STOP_LOSS = RISK_PROFILES["BALANCED"]["trailing_stop"]

# Legacy names for UI/script compatibility
DAILY_PROFIT_LIMIT = MAX_DAILY_PROFIT
DAILY_LOSS_LIMIT = MAX_DAILY_LOSS
TRAILING_STOP_DISTANCE = PER_TRADE_STOP_LOSS

# --- TRADING SETTINGS ---
INITIAL_BALANCE = 100000.00
SYMBOLS = ["BTC/USD"]
SEED_PRICES = {"BTC/USD": 50000.0}
SYMBOL_VOL = {"BTC/USD": 0.0015}
WARMUP_TICKS = 30
TICK_INTERVAL = 2
TRADING_MODE = "sim"
ALLOCATOR_DATA_DIR = "data_focus"
ALLOCATOR_TREND_WINDOW = 200
ALLOCATOR_VOL_WINDOW = 20
ALLOCATOR_REBALANCE_EVERY = 5
ALLOCATOR_CRASH_FILTER = True
ALLOCATOR_MARKET = "SPY"
ALLOCATOR_MAX_WEIGHT = 0.4
USE_VOL_SIZING = True
VOL_WINDOW = 20
STOP_ATR_MULT = 3.0
RISK_PER_TRADE_PCT = 0.01
MAX_POSITION_PCT = 0.5
MAX_GROSS_LEVERAGE = 1.0
MIN_CONFIDENCE = 0.6
