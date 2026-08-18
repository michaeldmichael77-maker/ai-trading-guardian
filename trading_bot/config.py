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
        "daily_loss_limit": 150.0,
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

# Initial active settings (Defaults to Balanced)
DAILY_PROFIT_LIMIT = RISK_PROFILES["BALANCED"]["daily_profit_limit"]
DAILY_LOSS_LIMIT = RISK_PROFILES["BALANCED"]["daily_loss_limit"]
TRAILING_STOP_DISTANCE = RISK_PROFILES["BALANCED"]["trailing_stop"]

# --- TRADING SETTINGS ---
INITIAL_BALANCE = 100000.00
SYMBOL = "BTC/ÕSD"
TRADE_AMOUNT = 1.0
TICK_INTERVAL = 2