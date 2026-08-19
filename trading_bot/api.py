"""FastAPI backend for the AI Trading Guardian (Full Version).

Orchestrates the Hive-Mind ensemble behind a stack of risk governors:
  * DailyGovernor  - profit target / loss limit / per-trade stop
  * Guardian       - real-time per-trade & portfolio risk verdict
  * PortfolioHeat  - exposure & correlation clustering
  * DrawdownRecovery - de-risking ladder
  * NewsEventFilter / SentimentOverlay - context gating
  * ExecutionQuality - slippage / latency tracking
  * AutoOptimizer  - online weight adaptation
"""

import collections
import os
import threading
import time

from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
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

app = FastAPI(title="AI Trading Guardian", version="1.0.0")


# --------------------------------------------------------------------------- #
# Password protection (required when exposed to the internet, e.g. on Render)
# --------------------------------------------------------------------------- #
# Paths reachable WITHOUT logging in.
_OPEN_PATHS = {"/login", "/do_login", "/healthz"}


@app.middleware("http")
async def _auth_gate(request: Request, call_next):
    # If no password is configured, the app is unlocked (local-use only).
    if not auth.is_enabled():
        return await call_next(request)

    path = request.url.path
    if path in _OPEN_PATHS or path.startswith("/static/login"):
        return await call_next(request)

    token = request.cookies.get(auth.COOKIE_NAME)
    if auth.verify_token(token):
        return await call_next(request)

    # Not logged in: send browsers to the login page, APIs a 401.
    if request.method == "GET" and "text/html" in request.headers.get("accept", ""):
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse({"error": "login required"}, status_code=401)


_LOGIN_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Trading Guardian — Login</title>
<style>
 body{background:#0d1117;color:#e6edf3;font-family:-apple-system,Segoe UI,Roboto,sans-serif;
   display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
 .box{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:32px;width:320px;text-align:center}
 h1{color:#58a6ff;font-size:1.2rem;margin:0 0 4px}
 p{color:#8b949e;font-size:.8rem;margin:0 0 20px}
 input{width:100%;padding:11px;background:#0d1117;border:1px solid #30363d;color:#e6edf3;
   border-radius:8px;font-size:1rem;box-sizing:border-box;margin-bottom:12px}
 button{width:100%;padding:12px;background:#238636;color:#fff;border:none;border-radius:8px;
   font-size:1rem;font-weight:700;cursor:pointer}
 .err{color:#f85149;font-size:.82rem;margin-bottom:10px;min-height:1em}
</style></head><body>
<form class="box" method="POST" action="/do_login">
  <h1>🛡️ AI Trading Guardian</h1>
  <p>Enter your password to continue</p>
  <div class="err">%ERR%</div>
  <input type="password" name="password" placeholder="Password" autofocus>
  <button type="submit">Log In</button>
</form></body></html>"""


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return _LOGIN_HTML.replace("%ERR%", "")


@app.post("/do_login")
async def do_login(password: str = Form("")):
    if auth.check_password(password):
        resp = RedirectResponse(url="/", status_code=302)
        secure = os.environ.get("GUARDIAN_HTTPS", "1") != "0"
        resp.set_cookie(auth.COOKIE_NAME, auth.make_token(), httponly=True,
                        samesite="lax", secure=secure, max_age=auth.SESSION_TTL)
        return resp
    return HTMLResponse(
        _LOGIN_HTML.replace("%ERR%", "Wrong password — try again."),
        status_code=401)


@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(auth.COOKIE_NAME)
    return resp


@app.get("/healthz")
async def healthz():
    return {"ok": True}

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

# --------------------------------------------------------------------------- #
# Shared mutable state
# --------------------------------------------------------------------------- #
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

# voter_name -> cumulative pnl credited (for the auto-optimizer)
voter_attribution = collections.defaultdict(float)
# symbol -> list of voter names that agreed with the open entry
entry_attribution = {}

price_buffers = {s: collections.deque(maxlen=200) for s in config.SYMBOLS}

logs = collections.deque(maxlen=300)


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    logs.appendleft(line)
    print(line)


# --------------------------------------------------------------------------- #
# Notifications / alerts (in-app feed + optional email)
# --------------------------------------------------------------------------- #
from trading_bot.notifications import NotificationCenter
notifier = NotificationCenter(logger=log)


# --------------------------------------------------------------------------- #
# Persistence (optional & failure-tolerant)
# --------------------------------------------------------------------------- #
storage = Storage(logger=log)

# Restore adaptive Hive-Mind weights learned in previous runs.
_saved_weights = storage.load_weights()
if _saved_weights:
    hive_mind.set_weights(_saved_weights)
    log(f"Restored Hive-Mind weights from previous runs: "
        f"{ {k: round(v, 2) for k, v in hive_mind.weights.items()} }")

# Last equity snapshot persisted (throttled to avoid hammering the DB).
_last_equity_save = 0.0


# --------------------------------------------------------------------------- #
# Live auto-executing trend allocator (the validated hands-off edge)
# --------------------------------------------------------------------------- #
from trading_bot.live_allocator import LiveAllocator

def _load_allocator_series():
    """Load daily CSV history for the allocator. Returns {} if unavailable."""
    import os as _os
    from trading_bot.engine.csv_market import CSVMarket
    data_dir = config.ALLOCATOR_DATA_DIR
    if not _os.path.isabs(data_dir):
        data_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)),
                                 data_dir)
    if not _os.path.isdir(data_dir):
        return {}
    try:
        m = CSVMarket(data_dir)
        n = min(len(v) for v in m.series.values())
        return {s: list(m.series[s])[-n:] for s in m.symbols}
    except Exception as exc:  # pragma: no cover - defensive
        log(f"Allocator data load failed: {exc}")
        return {}


_allocator_series = _load_allocator_series()
live_allocator = LiveAllocator(_allocator_series, notifier=notifier, logger=log)
# Step the allocator on a slow cadence relative to the tick loop so each "bar"
# represents a trading day in fast-forward for demonstration.
_alloc_step_every = 3       # advance one daily bar every N loop ticks
_alloc_tick_counter = 0


# --------------------------------------------------------------------------- #
# Broker manager — lets you switch between simulator / Alpaca paper / Alpaca live
# --------------------------------------------------------------------------- #
from trading_bot.brokers.simulator import SimulatorAdapter
from trading_bot.broker_manager import BrokerManager

_sim_adapter = SimulatorAdapter(market, portfolio, bot_state["last_prices"],
                                logger=log)
broker = BrokerManager(_sim_adapter, notifier=notifier, logger=log)
# Honor the startup trading mode from config/env (defaults to safe "sim").
if config.TRADING_MODE in ("paper", "live"):
    _ok, _info = broker.switch(config.TRADING_MODE)
    if not _ok:
        log(f"Startup broker mode '{config.TRADING_MODE}' not active: "
            f"{_info.get('error')}  (staying on simulator)")


# --------------------------------------------------------------------------- #
# Position sizing
# --------------------------------------------------------------------------- #
def position_size_and_risk(symbol, price, confidence, risk_multiplier):
    """Volatility-based sizing. Returns (units, risk_dollars).

    Mirrors the backtester exactly: risk a fixed small % of equity per trade
    with the stop placed STOP_ATR_MULT volatility-units away, capped by both a
    max-position notional and a worst-case overnight-gap tail-risk limit. This
    is what keeps real-data losses bounded (no more $800 hits on a $50 stop).
    """
    equity = portfolio.equity(bot_state["last_prices"])
    if config.USE_VOL_SIZING:
        from trading_bot.volatility import expected_move
        move = expected_move(list(price_buffers[symbol]), price,
                             window=config.VOL_WINDOW)
        stop_distance = max(move * config.STOP_ATR_MULT, 1e-9)
        risk_dollars = equity * config.RISK_PER_TRADE_PCT * confidence * risk_multiplier
        units = risk_dollars / stop_distance
    else:
        vol = config.SYMBOL_VOL.get(symbol, 0.0015)
        stop_distance = max(price * vol * 3.0, 0.01)
        risk_dollars = config.PER_TRADE_STOP_LOSS * confidence * risk_multiplier
        units = risk_dollars / stop_distance

    # Cap single-position notional.
    max_notional = equity * config.MAX_POSITION_PCT
    if units * price > max_notional:
        units = max_notional / price

    # Tail-risk cap: bound a worst-plausible overnight gap to MAX_SINGLE_LOSS_PCT.
    gap_cap = getattr(config, "MAX_SINGLE_LOSS_PCT", None)
    if gap_cap:
        assumed_gap = 0.25
        max_units_for_gap = (equity * gap_cap) / (price * assumed_gap)
        units = min(units, max_units_for_gap)

    units = max(0.0, round(units, 6))
    eff_risk = units * stop_distance
    return units, eff_risk


def position_size(symbol, price, confidence, risk_multiplier):
    """Backwards-compatible wrapper returning just the unit size."""
    units, _ = position_size_and_risk(symbol, price, confidence, risk_multiplier)
    return units


def buying_power_ok(symbol, price, size):
    """Reject a new entry that would push gross leverage past the cap.

    Applies to longs AND shorts: shorts credit cash but still add to gross
    exposure, so we measure total |notional| against equity * MAX_GROSS_LEVERAGE.
    """
    prices = bot_state["last_prices"]
    equity = portfolio.equity(prices)
    if equity <= 0:
        return False
    projected_gross = portfolio.gross_exposure(prices) + abs(size) * price
    return projected_gross <= equity * config.MAX_GROSS_LEVERAGE


# --------------------------------------------------------------------------- #
# Core trading tick
# --------------------------------------------------------------------------- #
def process_symbol(symbol):
    price = market.get_price(symbol)
    if price is None:
        return
    bot_state["last_prices"][symbol] = price
    price_buffers[symbol].append(price)
    sentiment_overlay.update(symbol)

    buf = list(price_buffers[symbol])
    if len(buf) < config.WARMUP_TICKS:
        return

    regime = regime_detector.detect_regime(buf)
    bot_state["regime_by_symbol"][symbol] = regime
    bot_state["current_regime"] = regime

    mtf_result = mtf.check_alignment(buf)
    senti = sentiment_overlay.get(symbol)

    decision = hive_mind.decide(buf, regime=regime, mtf=mtf_result, sentiment=senti)

    # --- managed exits: hard stop / take-profit / trailing stop ---
    # (always runs, even during a news blackout — we never trap a position)
    pos = portfolio.get_position(symbol)
    if pos["size"] != 0:
        verdict = exit_manager.check(symbol, pos, price)
        if verdict:
            _close(symbol, price, reason=verdict["reason"])
            return

    # Drawdown-aware confidence bar.
    min_conf = config.MIN_CONFIDENCE + drawdown_recovery.confidence_bonus

    # News blackout blocks *new entries* but not exits.
    blackout = news_filter.is_blackout()

    signal = decision["signal"]
    conf = decision["confidence"]

    # Opposite-signal exit (flatten before considering a reversal next tick).
    if signal == "SELL" and pos["size"] > 0:
        _close(symbol, price, reason="signal")
        return
    if signal == "BUY" and pos["size"] < 0:
        _close(symbol, price, reason="signal")
        return

    # New entry — either a long (BUY) or a short (SELL).
    if signal in ("BUY", "SELL") and pos["size"] == 0 and conf >= min_conf:
        if blackout:
            return
        # Proactive loss-limit guard: don't open new risk if a single per-trade
        # stop could push us past the daily loss limit. Protects the ceiling
        # BEFORE committing capital, not just after.
        if daily_governor.remaining_loss_budget() <= config.PER_TRADE_STOP_LOSS:
            return
        open_pos = portfolio.open_positions()
        equity = portfolio.equity(bot_state["last_prices"])
        allowed, why = heat_monitor.can_add_position(
            open_pos, equity, config.PER_TRADE_STOP_LOSS, symbol
        )
        if not allowed:
            return
        if not mtf_result["aligned"]:
            return
        size, risk_dollars = position_size_and_risk(
            symbol, price, conf, drawdown_recovery.risk_multiplier)
        if size <= 0:
            return
        if not buying_power_ok(symbol, price, size):
            return
        if signal == "BUY":
            fill = exec_quality.record_fill(symbol, price, "BUY")
            portfolio.execute_buy(symbol, fill["fill"], size)
            daily_governor.register_position(symbol, fill["fill"], size, "BUY")
        else:
            fill = exec_quality.record_fill(symbol, price, "SELL")
            portfolio.execute_short(symbol, fill["fill"], size)
            daily_governor.register_position(symbol, fill["fill"], size, "SELL")
        exit_manager.on_open(symbol, risk_dollars=risk_dollars)
        # Remember which voters agreed for attribution at close.
        entry_attribution[symbol] = [
            v["voter"] for v in decision["votes"] if v["signal"] == signal
        ]
        verb = "BUY" if signal == "BUY" else "SHORT"
        log(f"{verb} {size:g} {symbol} @ {fill['fill']:.2f} "
            f"(conf {conf:.0%}, {regime}, slip {fill['slippage_bps']}bps)")


def _close(symbol, price, reason="signal"):
    pos = portfolio.get_position(symbol)
    if pos["size"] == 0:
        return
    entry_price = pos["avg_price"]
    size = abs(pos["size"])
    if pos["size"] > 0:
        # Close a long: sell at the (slipped) bid.
        fill = exec_quality.record_fill(symbol, price, "SELL")
        result = portfolio.execute_sell(symbol, fill["fill"], pos["size"])
    else:
        # Cover a short: buy back at the (slipped) ask.
        fill = exec_quality.record_fill(symbol, price, "BUY")
        result = portfolio.execute_cover(symbol, fill["fill"], size)
    daily_governor.close_position(symbol)
    exit_manager.on_close(symbol)
    pnl = result["pnl"] if result else 0.0

    # Credit/charge the voters that opened this trade.
    for voter in entry_attribution.pop(symbol, []):
        voter_attribution[voter] += pnl
    storage.record_trade(symbol, entry_price, fill["fill"], size, pnl, reason)
    log(f"SELL {symbol} @ {fill['fill']:.2f} | {reason} | PnL ${pnl:,.2f}")


def flatten_all(reason="flatten"):
    """Immediately close EVERY open position. Used on limit breach / kill.

    This is what makes the daily loss limit a hard guarantee: the instant we
    breach, we are flat — positions cannot keep bleeding after the day ends.
    """
    closed = 0
    for symbol in list(portfolio.open_positions().keys()):
        _close(symbol, bot_state["last_prices"].get(symbol, 0.0), reason=reason)
        closed += 1
    return closed


# Track which limit alerts we've already sent today (avoid duplicate emails).
_alerted = {"approach_loss": False, "approach_profit": False}


def _check_approach_alerts():
    """Warn (once each) as the day's P&L approaches the loss/profit limits."""
    pnl = daily_governor.current_pnl
    max_loss = abs(daily_governor.limits.max_loss)
    max_profit = daily_governor.limits.max_profit

    # 70% of the way to the loss limit -> heads-up.
    if not _alerted["approach_loss"] and pnl <= -0.70 * max_loss:
        _alerted["approach_loss"] = True
        notifier.notify(
            "⚠️ Approaching daily loss limit",
            f"Daily P&L is ${pnl:,.2f} — that's 70% of the ${max_loss:,.0f} "
            f"limit. The Hive-Mind is de-risking. If it reaches the limit, all "
            f"positions auto-flatten and the day ends.",
            level="WARNING")

    if not _alerted["approach_profit"] and pnl >= 0.70 * max_profit:
        _alerted["approach_profit"] = True
        notifier.notify(
            "📈 Approaching daily profit target",
            f"Daily P&L is +${pnl:,.2f} — 70% of the ${max_profit:,.0f} target. "
            f"Getting close to locking in the day.",
            level="INFO")


def _persist_session(reason):
    """Record the just-finished trading session to the database."""
    try:
        gov = daily_governor.summary()
        equity = portfolio.equity(bot_state["last_prices"])
        storage.record_session(
            started=daily_governor.session_start or time.time(),
            ended=daily_governor.session_end or time.time(),
            start_equity=daily_governor.day_start_balance or equity,
            end_equity=equity,
            daily_pnl=gov["daily_pnl"],
            trades=gov["trades_today"],
            reason=reason,
        )
    except Exception as exc:  # defensive: never let persistence break shutdown
        log(f"session persist failed: {exc}")


def bot_loop():
    log("Trading loop initialised.")
    while True:
        try:
            if bot_state["is_running"] and bot_state["daily_governor_active"]:
                with state_lock:
                    if not daily_governor.should_continue_trading():
                        bot_state["is_running"] = False
                        reason = daily_governor.get_shutdown_reason()
                        # Guarantee we are flat when the day ends.
                        flatten_all(reason="DAY-END FLATTEN")
                        _persist_session(reason)
                        storage.save_weights(hive_mind.weights)
                        log(f"Trading day ended: {reason}")
                    else:
                        for symbol in config.SYMBOLS:
                            process_symbol(symbol)

                        prices = bot_state["last_prices"]
                        equity = portfolio.update_equity_curve(prices)
                        # Daily P&L is mark-to-market equity vs the day's
                        # starting equity (cash already nets realised P&L).
                        verdict = daily_governor.update_pnl(equity)

                        # --- HARD limit enforcement: flatten the instant a
                        #     limit is breached so losses cannot grow further.
                        if verdict and verdict.get("breach"):
                            n = flatten_all(reason=f"{verdict['breach']}-LIMIT FLATTEN")
                            bot_state["is_running"] = False
                            reason = daily_governor.get_shutdown_reason()
                            _persist_session(reason)
                            storage.save_weights(hive_mind.weights)
                            if verdict["breach"] == "LOSS":
                                notifier.notify(
                                    "🛑 Daily LOSS limit hit — trading stopped",
                                    f"{reason} Flattened {n} position(s). You are "
                                    f"now in cash and protected. No further losses "
                                    f"today. Daily P&L: ${daily_governor.current_pnl:,.2f}",
                                    level="CRITICAL")
                            else:
                                notifier.notify(
                                    "🎯 Daily PROFIT target hit — day locked in!",
                                    f"{reason} Flattened {n} position(s) and locked "
                                    f"in your gains. Daily P&L: "
                                    f"+${daily_governor.current_pnl:,.2f}",
                                    level="SUCCESS")
                            continue

                        # --- Early-warning alerts as we approach limits ---
                        _check_approach_alerts()

                        # Risk overlays.
                        guardian.assess(prices)
                        heat = heat_monitor.compute(
                            portfolio.open_positions(), equity,
                            config.PER_TRADE_STOP_LOSS,
                        )
                        bot_state["portfolio_heat"] = heat["heat_pct"]
                        bot_state["correlation_risk"] = heat["correlation_risk"]

                        dd = drawdown_recovery.update(equity, portfolio.peak_equity)
                        bot_state["drawdown_mode"] = dd["mode"]
                        bot_state["current_sentiment"] = sentiment_overlay.aggregate

                        opt_report = auto_optimizer.maybe_optimize(
                            portfolio.closed_trades, dict(voter_attribution)
                        )
                        # Persist newly-tuned weights whenever the optimizer ran.
                        if opt_report and opt_report.get("runs", 0) > 0:
                            storage.save_weights(hive_mind.weights)

                        # Throttled equity-curve persistence (every ~10s).
                        global _last_equity_save
                        if time.time() - _last_equity_save >= 10:
                            storage.record_equity(equity)
                            _last_equity_save = time.time()

                        bot_state["ticks"] += 1
            else:
                # Keep prices live for the chart even when idle.
                for symbol in config.SYMBOLS:
                    p = market.get_price(symbol)
                    if p is not None:
                        bot_state["last_prices"][symbol] = p
                        price_buffers[symbol].append(p)

            # --- Auto-executing trend allocator (runs independently of the
            #     intraday bot; advances one daily bar every few ticks) ---
            global _alloc_tick_counter
            if live_allocator.enabled:
                _alloc_tick_counter += 1
                if _alloc_tick_counter >= _alloc_step_every:
                    _alloc_tick_counter = 0
                    with state_lock:
                        live_allocator.step()
        except Exception as exc:  # keep the loop alive no matter what
            log(f"Loop error: {exc}")
        time.sleep(config.TICK_INTERVAL)


threading.Thread(target=bot_loop, daemon=True).start()


# --------------------------------------------------------------------------- #
# API endpoints
# --------------------------------------------------------------------------- #
@app.post("/start_day")
async def start_trading_day():
    if bot_state["is_running"]:
        return {"status": "error", "message": "System is already running"}
    success = daily_governor.start_new_day(portfolio.balance)
    if not success:
        return {"status": "error", "message": daily_governor.get_shutdown_reason()}
    portfolio.reset_daily()
    bot_state["is_running"] = True
    bot_state["daily_governor_active"] = True
    _alerted["approach_loss"] = False
    _alerted["approach_profit"] = False
    log("=== Trading day started — Hive-Mind online ===")
    notifier.notify(
        "✅ Trading day STARTED — Hive-Mind protecting you",
        f"Fully automated session is live. Hard daily loss limit: "
        f"${abs(daily_governor.limits.max_loss):,.0f} (positions auto-flatten if "
        f"reached). Profit target: ${daily_governor.limits.max_profit:,.0f}. "
        f"Per-trade stop: ${daily_governor.limits.per_trade_stop_loss:,.0f}. "
        f"You'll be alerted of every important event.",
        level="SUCCESS")
    return {"status": "started", "message": "Hive-Mind trading day has begun"}


@app.post("/kill_switch")
async def emergency_kill_switch():
    bot_state["is_running"] = False
    bot_state["daily_governor_active"] = False
    # Flatten all open positions at market.
    n = flatten_all(reason="KILL SWITCH")
    daily_governor.end_day("Emergency Kill Switch activated")
    _persist_session("Emergency Kill Switch activated")
    storage.save_weights(hive_mind.weights)
    log("=== KILL SWITCH — all positions flattened ===")
    notifier.notify(
        "🔴 KILL SWITCH activated",
        f"You manually stopped the system. Flattened {n} position(s); now in "
        f"cash. Daily P&L: ${daily_governor.current_pnl:,.2f}.",
        level="CRITICAL")
    return {"status": "killed", "message": "System shut down & positions flattened"}


@app.post("/end_day")
async def end_day():
    bot_state["is_running"] = False
    bot_state["daily_governor_active"] = False
    n = flatten_all(reason="END-DAY FLATTEN")
    daily_governor.end_day("Manual end of day")
    _persist_session("Manual end of day")
    storage.save_weights(hive_mind.weights)
    log("Trading day ended manually.")
    notifier.notify(
        "⏹️ Trading day ended (manual)",
        f"You ended the day. Flattened {n} position(s). "
        f"Final daily P&L: ${daily_governor.current_pnl:,.2f}.",
        level="INFO")
    return {"status": "ended", "message": "Trading day ended"}


@app.get("/status")
async def get_status():
    prices = bot_state["last_prices"]
    equity = portfolio.equity(prices)
    unrealised = portfolio.unrealised_pnl(prices)
    gov = daily_governor.summary()
    stats = portfolio.stats()

    positions = []
    for symbol, pos in portfolio.open_positions().items():
        cur = prices.get(symbol, pos["avg_price"])
        upnl = (cur - pos["avg_price"]) * pos["size"]
        positions.append({
            "symbol": symbol,
            "size": round(abs(pos["size"]), 4),
            "avg_price": round(pos["avg_price"], 2),
            "current_price": round(cur, 2),
            "unrealised_pnl": round(upnl, 2),
            "side": pos["side"],
        })

    return {
        "balance": round(portfolio.balance, 2),
        "equity": round(equity, 2),
        "daily_pnl": round(gov["daily_pnl"], 2),
        "unrealised_pnl": round(unrealised, 2),
        "paper_trading": not broker.adapter.is_live,
        "broker_mode": broker.mode,
        "broker_name": broker.adapter.name,
        "is_live": broker.adapter.is_live,
        "is_running": bot_state["is_running"],
        "daily_shutdown": not daily_governor.should_continue_trading(),
        "shutdown_reason": gov["shutdown_reason"],
        "ticks": bot_state["ticks"],

        # Risk / governance
        "risk_status": guardian.risk_status,
        "regime": bot_state["current_regime"],
        "regime_by_symbol": bot_state["regime_by_symbol"],
        "portfolio_heat": bot_state["portfolio_heat"],
        "correlation_risk": bot_state["correlation_risk"],
        "drawdown_mode": bot_state["drawdown_mode"],
        "daily_limits": {
            "max_profit": gov["max_profit"],
            "max_loss": gov["max_loss"],
            "per_trade_stop": gov["per_trade_stop"],
            "profit_progress": gov["profit_progress"],
            "loss_progress": gov["loss_progress"],
            "trades_today": gov["trades_today"],
            "remaining_loss_budget": round(
                daily_governor.remaining_loss_budget(), 2),
        },
        "notifications": notifier.unread_summary(),

        # Context overlays
        "news": news_filter.status(),
        "sentiment": sentiment_overlay.status(),

        # Execution & optimisation
        "execution_quality": exec_quality.summary(),
        "optimizer": auto_optimizer.status(),
        "hive_weights": {k: round(v, 3) for k, v in hive_mind.weights.items()},
        "hive_last_decision": hive_mind.last_decision,

        # Portfolio & performance
        "positions": positions,
        "position_count": len(positions),
        "performance": stats,
        "lifetime": storage.lifetime_stats(),

        # Market data for the chart
        "prices": {s: round(p, 4) for s, p in prices.items()},
        "logs": list(logs)[:60],
    }


@app.get("/history/{symbol}")
async def history(symbol: str):
    buf = list(price_buffers.get(symbol, []))
    return {"symbol": symbol, "prices": [round(p, 4) for p in buf]}


@app.get("/trades")
async def trades(limit: int = 50):
    """Persisted trade blotter (survives restarts)."""
    return {"trades": storage.recent_trades(limit=limit)}


@app.get("/equity_history")
async def equity_history(limit: int = 500):
    """Persisted equity-curve snapshots for charting."""
    return {"equity": storage.equity_history(limit=limit)}


@app.get("/sessions")
async def sessions(limit: int = 20):
    """Persisted daily session results."""
    return {"sessions": storage.recent_sessions(limit=limit)}


@app.get("/allocator")
async def allocator_view():
    """Current recommended allocation from the validated TrendAllocator.

    This is the 'big-dog' tactical-allocation edge: it reads real daily price
    history and returns which assets are in a confirmed uptrend, their inverse-
    volatility target weights, the crash-filter (risk-on/off) state, and the
    backtested performance vs. buy & hold. Pure analysis — it never trades your
    account automatically.
    """
    import os as _os
    from trading_bot.trend_allocator import TrendAllocator
    from trading_bot.allocator_backtest import AllocatorBacktest

    data_dir = config.ALLOCATOR_DATA_DIR
    if not _os.path.isabs(data_dir):
        data_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)),
                                 data_dir)
    if not _os.path.isdir(data_dir):
        return {"available": False,
                "message": f"No data at {data_dir}. Run: python3 -m "
                           f"trading_bot.fetch_data --out data_real_long --days 3650"}

    alloc = TrendAllocator(
        trend_window=config.ALLOCATOR_TREND_WINDOW,
        vol_window=config.ALLOCATOR_VOL_WINDOW,
        rebalance_every=config.ALLOCATOR_REBALANCE_EVERY,
        crash_filter=config.ALLOCATOR_CRASH_FILTER,
        market_symbol=config.ALLOCATOR_MARKET,
        max_weight=config.ALLOCATOR_MAX_WEIGHT,
    )
    try:
        bt = AllocatorBacktest(data_dir, allocator=alloc)
    except Exception as exc:  # pragma: no cover - defensive
        return {"available": False, "message": str(exc)}

    idx = bt.N - 1
    market_series = bt.series.get(config.ALLOCATOR_MARKET)
    risk_on = alloc.market_ok(market_series, idx)
    weights = alloc.target_weights(bt.series, idx, market_series)
    weights = {s: round(w, 4) for s, w in
               sorted(weights.items(), key=lambda kv: -kv[1])}
    cash_weight = round(max(0.0, 1.0 - sum(weights.values())), 4)

    # Performance summary (full + walk-forward OOS) and benchmark.
    full = bt.run()
    split = int(bt.N * 0.6)
    oos = bt.run(start=split)
    bh = bt.benchmark_buy_hold(config.ALLOCATOR_MARKET, start=split)

    return {
        "available": True,
        "risk_on": risk_on,
        "regime": "RISK-ON (invested)" if risk_on else "RISK-OFF (defensive cash)",
        "target_weights": weights,
        "cash_weight": cash_weight,
        "symbols_in_uptrend": list(weights.keys()),
        "as_of_bar": idx,
        "config": {
            "trend_window": alloc.trend_window,
            "vol_window": alloc.vol_window,
            "rebalance_every": alloc.rebalance_every,
            "crash_filter": alloc.crash_filter,
        },
        "performance": {
            "full_return_pct": full["return_pct"],
            "full_sharpe": full["sharpe"],
            "full_max_drawdown_pct": full["max_drawdown_pct"],
            "oos_return_pct": oos["return_pct"],
            "oos_sharpe": oos["sharpe"],
            "oos_max_drawdown_pct": oos["max_drawdown_pct"],
            "benchmark_oos_return_pct": bh["return_pct"] if bh else None,
            "benchmark_oos_max_drawdown_pct": bh["max_drawdown_pct"] if bh else None,
            "years": round(bt.N / 252, 1),
        },
    }


@app.get("/notifications")
async def get_notifications(limit: int = 50, since_id: int = 0):
    """In-app alert feed. The dashboard polls this; email is sent in parallel."""
    return {
        "notifications": notifier.recent(limit=limit, since_id=since_id),
        "summary": notifier.unread_summary(),
    }


@app.post("/set_loss_limit")
async def set_loss_limit(max_loss: float):
    """Update the daily loss limit. THIS IS THE ONLY WAY IT CHANGES.

    Per your non-negotiable: the daily loss ceiling is never altered
    automatically — only by an explicit manual call here.
    """
    if max_loss <= 0:
        return {"status": "error", "message": "max_loss must be positive"}
    old = daily_governor.limits.max_loss
    daily_governor.limits.max_loss = float(max_loss)
    notifier.notify(
        "⚙️ Daily loss limit changed (by you)",
        f"Daily loss limit changed from ${abs(old):,.2f} to ${max_loss:,.2f}.",
        level="WARNING")
    return {"status": "ok", "old": old, "new": max_loss}


@app.post("/set_limits")
async def set_limits(max_loss: float = None, max_profit: float = None,
                     per_trade_stop: float = None):
    """Manually adjust daily limits (you, and only you)."""
    changed = {}
    if max_loss is not None and max_loss > 0:
        changed["max_loss"] = (daily_governor.limits.max_loss, max_loss)
        daily_governor.limits.max_loss = float(max_loss)
    if max_profit is not None and max_profit > 0:
        changed["max_profit"] = (daily_governor.limits.max_profit, max_profit)
        daily_governor.limits.max_profit = float(max_profit)
    if per_trade_stop is not None and per_trade_stop > 0:
        changed["per_trade_stop"] = (daily_governor.limits.per_trade_stop_loss,
                                     per_trade_stop)
        daily_governor.limits.per_trade_stop_loss = float(per_trade_stop)
    if changed:
        notifier.notify("⚙️ Trading limits updated (by you)",
                        "; ".join(f"{k}: {v[0]}→{v[1]}" for k, v in changed.items()),
                        level="WARNING")
    return {"status": "ok", "changed": changed}


@app.post("/configure_email")
async def configure_email(address: str, password: str, send_to: str = None,
                          smtp_host: str = None, smtp_port: int = None):
    """Turn on email alerts from the dashboard (no terminal / restart needed).

    Auto-detects the mail server for common providers (Gmail, Outlook, Yahoo,
    iCloud, AOL). Credentials are kept in memory only and never written to disk.
    """
    ok, msg = notifier.configure_email(address, password, send_to=send_to,
                                       smtp_host=smtp_host, smtp_port=smtp_port)
    if ok:
        notifier.notify("📧 Email alerts enabled",
                        f"Alerts will be emailed to {notifier.email_to}. "
                        f"Sending a test now…", level="INFO", email=False)
    return {"status": "ok" if ok else "error", "message": msg,
            "config": notifier._config_summary()}


@app.post("/test_email")
async def test_email():
    """Send a one-off TEST email so you can confirm alerts work pre-session."""
    return notifier.send_test()


@app.post("/allocator/enable")
async def allocator_enable():
    """Turn on the validated, hands-off auto-rebalancing trend strategy."""
    if not live_allocator.symbols:
        return {"status": "error",
                "message": "No allocator data. Run: python3 -m "
                           "trading_bot.fetch_data --out data_focus --days 3650"}
    ok, msg = live_allocator.enable()
    return {"status": "ok" if ok else "error", "message": msg,
            "allocator": live_allocator.status()}


@app.post("/allocator/disable")
async def allocator_disable():
    live_allocator.disable()
    return {"status": "ok", "allocator": live_allocator.status()}


@app.post("/allocator/flatten")
async def allocator_flatten():
    """Sell all allocator holdings to cash (does not disable the engine)."""
    n = live_allocator.flatten()
    notifier.notify("💵 Allocator flattened to cash",
                    f"Sold {n} holding(s) to cash by your request.",
                    level="INFO")
    return {"status": "ok", "flattened": n, "allocator": live_allocator.status()}


@app.get("/allocator/live")
async def allocator_live():
    """Current state of the auto-executing allocator (holdings, equity, etc.)."""
    return live_allocator.status()


@app.get("/symbols")
async def list_symbols():
    """The full list of symbols the Hive-Mind is currently watching/trading."""
    return {"symbols": list(config.SYMBOLS)}


@app.post("/add_symbol")
async def add_symbol(symbol: str, start_price: float = None):
    """Add YOUR own symbol for the Hive-Mind to watch and trade.

    Futures use a leading "/" (e.g. /MGC for Micro Gold, /ZC for Corn,
    /HE for Lean Hogs/Livestock, /MCL for Micro Crude Oil). Known symbols get a
    realistic starting price automatically; for anything else you can pass
    ``start_price`` (defaults to 100).
    """
    symbol = symbol.strip().upper()
    if not symbol:
        return {"status": "error", "message": "Please provide a symbol."}
    if symbol in config.SYMBOLS:
        return {"status": "error", "message": f"{symbol} is already in the list."}

    known = getattr(config, "KNOWN_SYMBOLS", {})
    if symbol in known:
        price, vol = known[symbol]
    else:
        price = float(start_price) if start_price else 100.0
        vol = 0.0018
    if start_price:                      # explicit price always wins
        price = float(start_price)

    # Register everywhere the system expects the symbol to exist.
    config.SYMBOLS.append(symbol)
    config.SEED_PRICES[symbol] = price
    config.SYMBOL_VOL[symbol] = vol
    market.add_symbol(symbol, price)
    price_buffers[symbol] = collections.deque(maxlen=200)
    bot_state["last_prices"][symbol] = price
    sentiment_overlay.scores[symbol] = 0.0

    notifier.notify(
        "➕ Symbol added to watchlist",
        f"{symbol} added at ${price:,.2f}. The Hive-Mind will now watch and "
        f"may trade it once it has enough price history.",
        level="INFO")
    return {"status": "ok", "symbol": symbol, "start_price": price,
            "symbols": list(config.SYMBOLS)}


@app.post("/remove_symbol")
async def remove_symbol(symbol: str):
    """Stop watching a symbol. Any open position in it is closed first."""
    symbol = symbol.strip().upper()
    if symbol not in config.SYMBOLS:
        return {"status": "error", "message": f"{symbol} is not in the list."}
    # Close any open position so nothing is left dangling.
    if portfolio.get_position(symbol)["size"] != 0:
        _close(symbol, bot_state["last_prices"].get(symbol, 0.0),
               reason="symbol removed")
    config.SYMBOLS.remove(symbol)
    notifier.notify("➖ Symbol removed", f"{symbol} removed from the watchlist.",
                    level="INFO")
    return {"status": "ok", "symbol": symbol, "symbols": list(config.SYMBOLS)}


@app.get("/broker/status")
async def broker_status():
    """Which broker/mode is active (sim / paper / live) and whether keys exist."""
    return broker.status()


@app.post("/broker/switch")
async def broker_switch(mode: str):
    """Switch trading mode.

    mode = 'sim'   -> simulator (fake prices & money; the safe default)
    mode = 'paper' -> Alpaca PAPER (REAL prices, FAKE money)
    mode = 'live'  -> Alpaca LIVE (REAL money; hard-gated, needs opt-in)

    Switching is refused while a trading session is running — stop first so
    nothing is left half-executed across two different accounts.
    """
    if bot_state["is_running"] or live_allocator.enabled:
        return {"status": "error",
                "message": "Stop trading (End Day / Pause allocator) before "
                           "switching broker mode."}
    ok, info = broker.switch(mode)
    return {"status": "ok" if ok else "error",
            "info": info, "broker": broker.status()}


@app.get("/broker/account")
async def broker_account():
    """Live account snapshot from the active broker (sim or Alpaca)."""
    try:
        return {"status": "ok", "account": broker.adapter.get_account(),
                "positions": broker.adapter.get_positions(),
                "mode": broker.mode, "is_live": broker.adapter.is_live}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@app.post("/broker/set_keys")
async def broker_set_keys(key_id: str, secret_key: str):
    """Save your Alpaca keys (entered in the dashboard) for this session.

    Stored in memory only — never written to disk. This lets you connect
    without using the terminal.
    """
    has = broker.set_keys(key_id, secret_key)
    if not has:
        return {"status": "error",
                "message": "Both Key ID and Secret Key are required."}
    notifier.notify("🔑 Alpaca keys saved",
                    "Your Alpaca API keys were saved for this session. Use "
                    "'Test Connection' to verify them.", level="INFO")
    return {"status": "ok",
            "message": "Keys saved. Click 'Test Connection' to verify."}


@app.post("/broker/test")
async def broker_test(mode: str = "paper"):
    """Check your Alpaca keys work, WITHOUT changing your current mode."""
    return broker.test_connection(mode=mode)


@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")


import os
_static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
