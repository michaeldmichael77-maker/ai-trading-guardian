"""FastAPI backend for the AI Trading Guardian (Full Version)."""
import collections, os, threading, time, concurrent.futures
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from trading_bot import auth, config
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

app = FastAPI(title="AI Trading Guardian")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

market = MarketSimulator()
portfolio = Portfolio(balance=config.INITIAL_BALANCE)
guardian = Guardian(portfolio)
daily_governor = DailyGovernor(DailyLimits(max_profit=config.MAX_DAILY_PROFIT, max_loss=config.MAX_DAILY_LOSS, per_trade_stop_loss=config.PER_TRADE_STOP_LOSS))
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
bot_state = {"is_running": False, "daily_governor_active": False, "paper_trading": True, "current_regime": "UNKNOWN", "regime_by_symbol": {}, "portfolio_heat": 0.0, "correlation_risk": "LOW", "current_sentiment": 0.0, "drawdown_mode": "NORMAL", "last_prices": dict(config.SEED_PRICES), "ticks": 0}
price_buffers = {s: collections.deque(maxlen=200) for s in config.SYMBOLS}
logs = collections.deque(maxlen=300)

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"; logs.appendleft(line); print(line)

from trading_bot.notifications import NotificationCenter
notifier = NotificationCenter(logger=log)
storage = Storage(logger=log)
from trading_bot.brokers.simulator import SimulatorAdapter
from trading_bot.broker_manager import BrokerManager
_sim_adapter = SimulatorAdapter(market, portfolio, bot_state["last_prices"], logger=log)
broker = BrokerManager(_sim_adapter, notifier=notifier, logger=log)

def process_symbol(symbol):
    price = market.get_price(symbol)
    if price is None: return
    bot_state["last_prices"][symbol] = price
    price_buffers[symbol].append(price)
    sentiment_overlay.update(symbol)
    buf = list(price_buffers[symbol])
    if len(buf) < config.WARMUP_TICKS: return
    regime = regime_detector.detect_regime(buf)
    bot_state["regime_by_symbol"][symbol] = regime
    mtf_result = mtf.check_alignment(buf)
    decision = hive_mind.decide(buf, regime=regime, mtf=mtf_result, sentiment=sentiment_overlay.get(symbol))
    pos = portfolio.get_position(symbol)
    if pos["size"] != 0:
        verdict = exit_manager.check(symbol, pos, price)
        if verdict: _close(symbol, price, reason=verdict["reason"])
    if decision["signal"] in ("BUY", "SELL") and pos["size"] == 0:
        if decision["confidence"] >= config.MIN_CONFIDENCE:
            if decision["signal"] == "BUY": portfolio.execute_buy(symbol, price, 1.0)
            else: portfolio.execute_short(symbol, price, 1.0)
            log(f"{decision['signal']} {symbol} @ {price:.2f}")

def _close(symbol, price, reason="signal"):
    pos = portfolio.get_position(symbol)
    if pos["size"] == 0: return
    pnl = (price - pos["avg_price"]) * pos["size"] if pos["size"] > 0 else (pos["avg_price"] - price) * abs(pos["size"])
    if pos["size"] > 0:
        portfolio.execute_sell(symbol, price, pos["size"])
    else:
        portfolio.execute_cover(symbol, price, abs(pos["size"]))
    log(f"CLOSED {symbol} @ {price:.2f} | {reason} | PnL ${pnl:.2f}")

def bot_loop():
    log("HF Loop Active.")
    while True:
        try:
            if bot_state["is_running"]:
                with state_lock:
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        executor.map(process_symbol, config.SYMBOLS)
                bot_state["ticks"] += 1
            else:
                for s in config.SYMBOLS:
                    p = market.get_price(s)
                    if p: bot_state["last_prices"][s] = p
        except Exception as e: log(f"Loop error: {e}")
        time.sleep(config.TICK_INTERVAL)

threading.Thread(target=bot_loop, daemon=True).start()

@app.get("/")
async def read_index():
    return FileResponse('trading_bot/static/index.html')

@app.get("/status")
async def get_status():
    prices = bot_state["last_prices"]; gov = daily_governor.summary()
    return {"balance": round(portfolio.balance, 2), "equity": round(portfolio.balance, 2), "daily_pnl": round(gov["daily_pnl"], 2), "unrealised_pnl": 0.0, "is_running": bot_state["is_running"], "price": list(prices.values())[0], "prices": prices, "signal": hive_mind.last_decision.get("signal", "HOLD"), "hive_last_decision": hive_mind.last_decision, "regime": {"type": bot_state["current_regime"], "color": "#00ff88", "score": 0}, "connection": broker.mode, "broker_mode": broker.mode, "performance": portfolio.stats(), "execution_quality": exec_quality.summary(), "optimizer": auto_optimizer.status(), "sentiment": {"aggregate": sentiment_overlay.aggregate}, "logs": list(logs)[:40]}

@app.post("/toggle")
async def toggle_bot(): bot_state["is_running"] = not bot_state["is_running"]; return {"running": bot_state["is_running"]}

@app.post("/start_day")
async def start_day(): bot_state["is_running"] = True; bot_state["daily_governor_active"] = True; return {"status": "started"}

@app.post("/kill_switch")
async def kill_switch(): bot_state["is_running"] = False; return {"status": "killed"}

# Missing endpoints for UI
@app.get("/notifications")
async def notifications(): return {"notifications": [], "summary": {"unread": 0}}
@app.get("/trades")
async def get_trades(): return {"trades": []}
@app.get("/equity_history")
async def eq_hist(): return {"equity": []}
@app.get("/allocator/live")
async def alloc_live(): return {"available": False}
@app.get("/allocator")
async def alloc(): return {"available": False}

app.mount("/static", StaticFiles(directory="trading_bot/static"), name="static")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
