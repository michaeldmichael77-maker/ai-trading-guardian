"""Global configuration for the AI Trading Guardian."""

# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------
INITIAL_BALANCE = 100_000.0

# ---------------------------------------------------------------------------
# Loop timing
# ---------------------------------------------------------------------------
TICK_INTERVAL = 1.0          # seconds between market ticks
WARMUP_TICKS = 30            # ticks needed before strategies activate

# ---------------------------------------------------------------------------
# Daily governor limits (the "guardrails")
# ---------------------------------------------------------------------------
MAX_DAILY_PROFIT = 7_000.0   # lock in the day once we hit this
MAX_DAILY_LOSS = 175.0       # HARD stop for the day (non-negotiable ceiling)
PER_TRADE_STOP_LOSS = 50.0   # max dollar loss tolerated on a single position

# Safety buffer for the daily loss limit. We halt + flatten when the loss
# reaches this fraction of MAX_DAILY_LOSS, so that slippage on the flattening
# orders cannot push the realised loss past the configured maximum. 0.90 means
# "stop at 90% of the limit". This makes MAX_DAILY_LOSS an effective HARD cap.
DAILY_LOSS_SAFETY_BUFFER = 0.90

# ---------------------------------------------------------------------------
# Strategy / execution
# ---------------------------------------------------------------------------
MIN_CONFIDENCE = 0.60        # minimum hive-mind confidence to act
MAX_OPEN_POSITIONS = 6       # diversification cap
MAX_PORTFOLIO_HEAT = 0.06    # 6% of equity at risk across all open trades
BASE_RISK_PER_TRADE = 0.005  # 0.5% of equity risked per trade (pre-sizing)
MAX_GROSS_LEVERAGE = 1.5     # cap total |notional| (long+short) at 1.5x equity

# ---------------------------------------------------------------------------
# Exit management (take-profit & trailing stop). All "R" values are multiples
# of the per-trade dollar risk (PER_TRADE_STOP_LOSS).
# ---------------------------------------------------------------------------
# Backtest-tuned across 7 seeds: a fixed take-profit caps winners and hurts
# returns; letting profits run under a trailing stop dominated on return,
# Sharpe, win-rate AND profit-factor. So TP is disabled by default (set >0 to
# re-enable a hard target).
TAKE_PROFIT_R = 0.0          # 0 = disabled; let winners run under the trail
TRAIL_ACTIVATE_R = 1.0       # arm the trailing stop once profit reaches +1R
TRAIL_GIVEBACK = 0.5         # exit if profit gives back >50% of its peak

# ---------------------------------------------------------------------------
# Volatility-based risk sizing (the real fix for oversized positions).
#
# Instead of a fixed dollar stop calibrated for 1-second ticks, we risk a fixed
# small fraction of equity per trade and place the stop a volatility-multiple
# away from entry. This adapts automatically to bar granularity (tick/min/hour/
# day) so losses stay bounded and consistent on REAL data.
# ---------------------------------------------------------------------------
USE_VOL_SIZING = True        # master switch for volatility-based sizing/stops
RISK_PER_TRADE_PCT = 0.0010  # risk 0.10% of equity per trade (conservative)
STOP_ATR_MULT = 2.0          # stop distance = 2.0 x per-bar volatility move
VOL_WINDOW = 20              # lookback bars for volatility estimate
MAX_POSITION_PCT = 0.06      # cap any single position at 6% of equity notional

# Hard cap: the maximum % of equity a single overnight GAP can cost. Positions
# are additionally sized so that even a worst-case adverse move bounded by this
# fraction cannot exceed it. This is the floor under tail-risk that gaps create
# (you cannot stop out while the market is closed).
MAX_SINGLE_LOSS_PCT = 0.005  # never let one position lose more than 0.5% equity

# ---------------------------------------------------------------------------
# Transaction costs (must be modeled to judge a strategy honestly).
# ---------------------------------------------------------------------------
COMMISSION_PER_TRADE = 0.0   # flat $ per fill (many brokers are $0 now)
COMMISSION_BPS = 1.0         # round-turn cost proxy in basis points of notional

# ---------------------------------------------------------------------------
# Tradable universe with seed prices and rough annualised vol used by the
# market simulator.  Mix of crypto, equities, ETFs and futures.
# ---------------------------------------------------------------------------
SYMBOLS = [
    "BTCUSD", "ETHUSD", "SOLUSD", "AVAXUSD",
    "AAPL", "TSLA", "NVDA", "GOOGL",
    "MSFT", "AMZN", "META", "AMD",
    "QQQ", "SPY", "IWM", "TQQQ",
    "/ES", "/NQ", "/CL", "/GC",
]

SEED_PRICES = {
    "BTCUSD": 68000.0, "ETHUSD": 3500.0, "SOLUSD": 165.0, "AVAXUSD": 38.0,
    "AAPL": 195.0, "TSLA": 240.0, "NVDA": 122.0, "GOOGL": 178.0,
    "MSFT": 430.0, "AMZN": 185.0, "META": 500.0, "AMD": 160.0,
    "QQQ": 470.0, "SPY": 540.0, "IWM": 205.0, "TQQQ": 70.0,
    "/ES": 5400.0, "/NQ": 19000.0, "/CL": 78.0, "/GC": 2350.0,
}

# Per-tick volatility (fraction of price) used by the simulator.
SYMBOL_VOL = {
    "BTCUSD": 0.0025, "ETHUSD": 0.0030, "SOLUSD": 0.0045, "AVAXUSD": 0.0050,
    "AAPL": 0.0012, "TSLA": 0.0030, "NVDA": 0.0028, "GOOGL": 0.0015,
    "MSFT": 0.0011, "AMZN": 0.0018, "META": 0.0020, "AMD": 0.0030,
    "QQQ": 0.0010, "SPY": 0.0008, "IWM": 0.0014, "TQQQ": 0.0030,
    "/ES": 0.0009, "/NQ": 0.0012, "/CL": 0.0025, "/GC": 0.0010,
}

# Correlation clusters used by the heat monitor.
CORRELATION_GROUPS = {
    "CRYPTO": ["BTCUSD", "ETHUSD", "SOLUSD", "AVAXUSD"],
    "MEGA_TECH": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "AMD", "TSLA"],
    "INDEX": ["QQQ", "SPY", "IWM", "TQQQ", "/ES", "/NQ"],
    "COMMODITY": ["/CL", "/GC"],
}

# ---------------------------------------------------------------------------
# Trend Allocator ("big-dog edge") — validated on ~10y real data, walk-forward.
# These defaults are the ROBUST, untuned, industry-standard values that held up
# out-of-sample (OOS ret ~+104%, Sharpe ~1.39, maxDD ~12% vs SPY ~19-34%).
# ---------------------------------------------------------------------------
ALLOCATOR_TREND_WINDOW = 200     # long-term trend filter (bars)
ALLOCATOR_VOL_WINDOW = 40        # inverse-vol sizing lookback (bars)
ALLOCATOR_REBALANCE_EVERY = 5    # rebalance cadence (bars ~ weekly)
ALLOCATOR_CRASH_FILTER = True    # only take risk when SPY is above its trend
ALLOCATOR_MARKET = "SPY"         # market proxy for the crash filter
ALLOCATOR_MAX_WEIGHT = 0.35      # cap any single holding
ALLOCATOR_DATA_DIR = "data_focus"   # focused growth+diversifier universe
# (data_real_long = wider 18-symbol set; data_focus = 12 names that beat the
#  benchmark OOS on both return AND drawdown. Either works.)

# ---------------------------------------------------------------------------
# Known futures / common symbols, so when YOU add one it starts at a realistic
# price with sensible volatility. (You can add ANY symbol; unknown ones just
# get generic defaults.) Futures use a leading "/" by convention.
# ---------------------------------------------------------------------------
KNOWN_SYMBOLS = {
    # symbol      : (seed_price, per_tick_vol)
    "/GC":  (2350.0, 0.0010),   # Gold
    "/MGC": (2350.0, 0.0010),   # Micro Gold
    "/SI":  (30.0,   0.0018),   # Silver
    "/SIL": (30.0,   0.0018),   # Micro Silver
    "/CL":  (78.0,   0.0025),   # Crude Oil
    "/MCL": (78.0,   0.0025),   # Micro Crude Oil
    "/NG":  (2.8,    0.0035),   # Natural Gas
    "/ZC":  (440.0,  0.0018),   # Corn
    "/ZW":  (560.0,  0.0020),   # Wheat
    "/ZS":  (1180.0, 0.0018),   # Soybeans
    "/LE":  (185.0,  0.0014),   # Live Cattle
    "/HE":  (90.0,   0.0016),   # Lean Hogs (Livestock)
    "/GF":  (255.0,  0.0015),   # Feeder Cattle
    "/ES":  (5400.0, 0.0009),   # S&P 500 E-mini
    "/MES": (5400.0, 0.0009),   # Micro S&P 500
    "/NQ":  (19000.0,0.0012),   # Nasdaq E-mini
    "/MNQ": (19000.0,0.0012),   # Micro Nasdaq
    "/RTY": (2050.0, 0.0014),   # Russell 2000
    "/YM":  (40000.0,0.0010),   # Dow E-mini
    "/6E":  (1.08,   0.0007),   # Euro FX
    "/ZB":  (118.0,  0.0008),   # 30Y Treasury Bond
}

# ---------------------------------------------------------------------------
# Broker / trading mode.
#   "sim"   = built-in simulator (fake prices, fake money) — the safe default
#   "paper" = Alpaca PAPER (real market prices, FAKE money) — recommended next
#   "live"  = Alpaca LIVE (REAL money) — requires explicit, deliberate opt-in
# Keys are read from env vars so they are never committed to disk:
#   ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY
# ---------------------------------------------------------------------------
import os as _os
TRADING_MODE = _os.environ.get("GUARDIAN_TRADING_MODE", "sim")
ALPACA_API_KEY_ID = _os.environ.get("ALPACA_API_KEY_ID", "")
ALPACA_API_SECRET_KEY = _os.environ.get("ALPACA_API_SECRET_KEY", "")
# Extra guard: live trading is refused unless this is explicitly set to "1".
ALLOW_LIVE_TRADING = _os.environ.get("GUARDIAN_ALLOW_LIVE", "0") == "1"
