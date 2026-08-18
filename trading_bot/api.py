from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import threading
import time
import collections
import os

from trading_bot import config
from trading_bot.engine.market import MarketSimulator, AlpacaConnector
from trading_bot.engine.portfolio import Portfolio
from trading_bot.engine.guardian import Guardian
from trading_bot.engine.strategy import AIStrategy
from trading_bot.engine.regime_detector import RegimeDetector

app = FastAPI(title="AI Trading Guardian")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class RiskSettings(BaseModel):
    profit_limit: float
    loss_limit: float
    trailing_stop: float

class AlpacaKeys(BaseModel):
    api_key: str
    secret_key: str

market = MarketSimulator()
portfolio = Portfolio(balance=100000.0)
guardian = Guardian(portfolio)
ai_brain = AIStrategy()
regime_detector = RegimeDetector()
price_buffer = collections.deque(maxlen=100)

bot_state = { 
    "is_running": False, 
    "last_price": 0.0, 
    "signal": "STANDBY", 
    "pnl": 0.0, 
    "connection": "SIMULATOR",
    "regime": {"type": "UNKNOWN", "score": 0.0, "color": "#707a8a"}
}

def bot_loop():
    global bot_state, market
    while True:
        if bot_state["is_running"]:
            price = market.get_price()
            bot_state["last_price"] = price
            price_buffer.append(price)
            
            # 1. Market Regime Detection (New)
            bot_state["regime"] = regime_detector.analyze(list(price_buffer))
            
            # 2. AI Strategy Logic
            # Only generate signals if regime is not CHOPPY
            if len(price_buffer) >= 20:
                if bot_state["regime"]["type"] != "CHOPPY":
                    bot_state["signal"], _ = ai_brain.analyze(list(price_buffer))
                else:
                    bot_state["signal"] = "WAIT (CHOPPY)"
            
            # 3. Guardian Risk Check
            risk_status = guardian.check_risk_limits(price)
            if risk_status == "KILL_SWITCH":
                bot_state["is_running"] = False
            
            bot_state["pnl"] = portfolio.daily_pnl
        time.sleep(1)

threading.Thread(target=bot_loop, daemon=True).start()

@app.get("/status")
async def get_status():
    return { 
        "is_running": bot_state["is_running"], 
        "price": bot_state["last_price"], 
        "balance": portfolio.balance, 
        "daily_pnl": portfolio.daily_pnl, 
        "signal": bot_state["signal"], 
        "connection": bot_state["connection"],
        "regime": bot_state["regime"]
    }

@app.post("/toggle")
async def toggle_bot():
    bot_state["is_running"] = not bot_state["is_running"]
    return { "running": bot_state["is_running"] }

@app.post("/settings")
async def update_settings(settings: RiskSettings):
    guardian.update_settings(settings.profit_limit, settings.loss_limit, settings.trailing_stop)
    return {"status": "updated"}

@app.post("/connect")
async def connect_alpaca(keys: AlpacaKeys):
    global market
    try:
        new_market = AlpacaConnector(keys.api_key, keys.secret_key)
        if new_market.api:
            market = new_market
            bot_state["connection"] = "ALPACA"
            return {"status": "connected"}
    except: pass
    return {"status": "failed"}

app.mount("/static", StaticFiles(directory="trading_bot/static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse('trading_bot/static/index.html')

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
