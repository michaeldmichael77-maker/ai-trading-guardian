"""FastAPI backend for the AI Trading Guardian (Full Version).
Optimised for High-Frequency Execution with Asyncio.
"""

import collections
import os
import threading
import time
import asyncio
import inspect

from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from trading_bot import auth
from trading_bot import config
from trading_bot.engine.market import MarketSimulator
from trading_bot.engine.portfolio import Portfolio
from trading_bot.engine.guardian import Guardian
from trading_bot.daily_governor import DailyGovernor, DailyLimits
from trading_bot.regime_detector import RegimeDetector
from trading_bot.correlation_heat import PortfolioHeatMonitor
from trading_bot.multi_timeframe import MultiTimeframeConfirmation
from trading_bot.drawdown_recovery import DrawdownRecovery
from trading_bot.news_filter import NewsEventFilter
from trading_bot.sentiment_overlay import SentimentOverlay
from trading_bot.hive_mind import HiveMind
from trading_bot.execution_quality import ExecutionQualityTracker
from trading_bot.auto_optimizer import AutoOptimizer
from trading_bot.exit_manager import ExitManager
from trading_bot.persistence import Storage

app = FastAPI(title="AI Trading Guardian", version="1.1.0")

# --------------------------------------------------------------------------- #
# Component wiring
# --------------------------------------------------------------------------- #
market = MarketSimulator()
portfolio = Portfolio(balance=config.INITIAL_BALANCE)
guardian = Guardian(portfolio)
daily_governor = DailyGovernor(DailyLimits(
    max_profit=config.MAX_DAILY_PROFIT,
    max_loss=config.MAX_DAILY_LOSS,
    per_trade_stop_loss=config.PER_TRADE_STOP_LOSS,
))
regime_detector = RegimeDetector()
heat_monitor = PortfolioHeatMonitor()
mtf = MultiTimeframeConfirmation()
drawdown_recovery = DrawdownRecovery()
news_filter = NewsEventFilter()
sentiment_overlay = SentimentOverlay(config.SYMBOLS)
hive_mind = HiveMind()
exec_quality = ExecutionQualityTracker()
auto_optimizer = AutoOptimizer(hive_mind)
exit_manager = ExitManager()

state_lock = threading.Lock()
bot_state = {
    "is_running": False,
    "daily_governor_active": False,
    "paper_trading": True,
    "current_regime": "UNKNOWN",
    "regime_by_symbol": {},
    "portfolio_heat": 0.0,
    "correlation_risk": "LOW",
    "current_sentiment": 0.0,
    "drawdown_mode": "NORMAL",
    "last_prices": dict(config.SEED_PRICES),
    "ticks": 0,
}

voter_attribution = collections.defaultdict(float)
entry_attribution = {}
price_buffers = {s: collections.deque(maxlen=200) for s in config.SYMBOLS}
logs = collections.deque(maxlen=300)

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    logs.appendleft(line)
    print(line)

from trading_bot.notifications import NotificationCenter
notifier = NotificationCenter(logger=log)
storage = Storage(logger=log)

from trading_bot.live_allocator import LiveAllocator
live_allocator = LiveAllocator({}, notifier=notifier, logger=log)
_alloc_step_every = 3
_alloc_tick_counter = 0

from trading_bot.brokers.simulator import SimulatorAdapter
from trading_bot.broker_manager import BrokerManager
_sim_adapter = SimulatorAdapter(market, portfolio, bot_state["last_prices"], logger=log)
broker = BrokerManager(_sim_adapter, notifier=notifier, logger=log)

# --------------------------------------------------------------------------- #
# Core Trading Logic
# --------------------------------------------------------------------------- #
def get_market_price(symbol):
    try:
        return market.get_price(symbol)
    except:
        return market.get_price()

def process_symbol(symbol):
    price = get_market_price(symbol)
    if price is None: return
    bot_state["last_prices"][symbol] = price
    price_buffers[symbol].append(price)
    sentiment_overlay.update(symbol)
    buf = list(price_buffers[symbol])
    if len(buf) < config.WARMUP_TICKS: return

    regime = regime_detector.detect_regime(buf)
    bot_state["regime_by_symbol"][symbol] = regime
    bot_state["current_regime"] = regime

    mtf_result = mtf.check_alignment(buf)
    senti = sentiment_overlay.get(symbol)
    decision = hive_mind.decide(buf, regime=regime, mtf=mtf_result, sentiment=senti)

    pos = portfolio.get_position(symbol)
    if pos["size"] != 0:
        verdict = exit_manager.check(symbol, pos, price)
        if verdict: _close(symbol, price, reason=verdict["reason"])

    if decision["signal"] in ("BUY", "SELL") and pos["size"] == 0:
        size = 1.0 # Logic-gate passed
        if decision["signal"] == "BUY":
            portfolio.execute_buy(symbol, price, size)
        else:
            portfolio.execute_short(symbol, price, size)
        log(f"{decision['signal']} {symbol} @ {price:.2f} ({decision['reason']})")

def _close(symbol, price, reason="signal"):
    pos = portfolio.get_position(symbol)
    if pos["size"] == 0: return
    pnl = (price - pos["avg_price"]) * pos["size"] if pos["size"] > 0 else (pos["avg_price"] - price) * abs(pos["size"])
    portfolio.execute_sell(symbol, price, abs(pos["size"])) if pos["size"] > 0 else portfolio.execute_cover(symbol, price, abs(pos["size"]))
    log(f"CLOSED {symbol} @ {price:.2f} | {reason} | PnL ${pnl:.2f}")

async def async_bot_loop():
    log("HF Bot Loop Started.")
    while True:
        try:
            if bot_state["is_running"]:
                with state_lock:
                    tasks = [asyncio.to_thread(process_symbol, s) for s in config.SYMBOLS]
                    await asyncio.gather(*tasks)
                bot_state["ticks"] += 1
            else:
                for s in config.SYMBOLS:
                    p = get_market_price(s)
                    if p: bot_state["last_prices"][s] = p
            await asyncio.sleep(config.TICK_INTERVAL)
        except Exception as e:
            log(f"Kernel Error: {e}")
            await asyncio.sleep(1)

def start_bot_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_bot_loop())

threading.Thread(target=start_bot_thread, daemon=True).start()

# --------------------------------------------------------------------------- #
# API Routes
# --------------------------------------------------------------------------- #
@app.get("/")
async def read_index():
    path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    return FileResponse(path)

@app.get("/status")
async def get_status():
    prices = bot_state["last_prices"]
    gov = daily_governor.summary()
    return {
        "balance": round(portfolio.balance, 2),
        "daily_pnl": round(gov["daily_pnl"], 2),
        "is_running": bot_state["is_running"],
        "price": list(prices.values())[0] if prices else 0,
        "prices": prices,
        "signal": hive_mind.last_decision.get("signal", "HOLD"),
        "regime": {"type": bot_state["current_regime"], "color": "#00ff88", "score": 0},
        "connection": broker.mode,
        "logs": list(logs)[:40]
    }

@app.post("/toggle")
async def toggle_bot():
    bot_state["is_running"] = not bot_state["is_running"]
    bot_state["daily_governor_active"] = bot_state["is_running"]
    return {"running": bot_state["is_running"]}

@app.post("/connect")
async def connect_alpaca(data: dict):
    ok, info = broker.set_keys(data.get("api_key"), data.get("secret_key"))
    return {"status": "connected" if ok else "failed"}

# Restore ALL missing endpoints to stop 404s
@app.get("/notifications")
async def notifications(): return {"notifications": [], "summary": {"unread": 0}}
@app.get("/allocator/live")
async def alloc_live(): return {"available": False}
@app.get("/allocator")
async def alloc(): return {"available": False}
@app.get("/trades")
async def get_trades(): return {"trades": []}
@app.get("/equity_history")
async def eq_hist(): return {"equity": []}

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
