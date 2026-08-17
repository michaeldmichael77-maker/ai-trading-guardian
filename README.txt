==========================================================================
 TradingApp_Full — AI Trading Guardian (Full Version)
==========================================================================

A complete, self-contained automated paper-trading platform built around the
"Hive-Mind" strategy ensemble and a layered stack of risk governors. It runs
with zero external API keys (built-in market simulator) and ships with a
professional WeBull-style web dashboard featuring a live candlestick chart.

--------------------------------------------------------------------------
 HOW TO RUN
--------------------------------------------------------------------------
1. Open a terminal and go to the project folder:
     cd TradingApp_Full

2. Install requirements:
     pip3 install --user -r requirements.txt

3. Start the app:
     PYTHONPATH=. python3 trading_bot/main.py

4. Open your browser to:
     http://localhost:8000/static/index.html
   (the root URL "/" also redirects there)

5. Click "START TRADING DAY" to begin. The system warms up for ~30 seconds
   (collecting data) before the Hive-Mind starts placing trades.

Controls:
  ▶ START TRADING DAY  - begins a governed trading session
  ■ END DAY            - cleanly ends the session
  ⚠ KILL SWITCH        - flattens ALL positions and shuts down immediately

--------------------------------------------------------------------------
 WHAT THE SYSTEM DOES AUTOMATICALLY
--------------------------------------------------------------------------
- Streams simulated market data for 20 symbols (crypto, equities, ETFs, futures)
- Runs the Hive-Mind ensemble (5 technical voters) on every symbol
- Adapts voter trust to the detected market regime
- Requires multi-timeframe alignment before entering
- Trades BOTH directions: goes long on BUY signals and short on SELL signals
- Sizes each position so the per-trade stop is ~$50
- Enforces a $50 per-trade stop-loss on every open position (long or short)
- Banks/protects gains with a trailing stop (and optional take-profit target)
- Locks in the day at +$7,000 profit or halts at -$175 loss
- Monitors portfolio heat and correlation-cluster concentration
- De-risks automatically during drawdowns (CAUTIOUS / DEFENSIVE / LOCKDOWN)
- Blocks new entries during simulated high-impact news windows
- Tilts conviction with a market sentiment overlay
- Tracks execution quality (slippage, latency, fill quality score)
- Continuously self-tunes voter weights via the Auto Optimizer

--------------------------------------------------------------------------
 ARCHITECTURE  (trading_bot/)
--------------------------------------------------------------------------
  main.py                 Entry point (uvicorn launcher)
  api.py                  FastAPI backend + the live trading loop
  config.py               Symbols, seed prices, limits, all tunables
  hive_mind.py            Weighted ensemble + regime/MTF/sentiment fusion
  daily_governor.py       Profit target / loss limit / per-trade stop / session
  regime_detector.py      TRENDING_UP/DOWN, RANGING, VOLATILE classification
  multi_timeframe.py      Fast/mid/slow trend alignment gate
  correlation_heat.py     Portfolio heat % + correlation cluster risk
  drawdown_recovery.py    Adaptive de-risking ladder
  news_filter.py          Simulated economic-event blackout windows
  sentiment_overlay.py    Mean-reverting per-symbol sentiment scores
  execution_quality.py    Slippage / latency / fill-quality tracking (shared
                          fill model used by BOTH live and backtest paths)
  auto_optimizer.py       Online reward-weighted voter-weight tuning
  exit_manager.py         Centralised exits: hard stop / take-profit / trailing
                          stop (two-sided: long & short)
  persistence.py          SQLite storage (trades, sessions, equity, weights)
  backtest.py             Deterministic backtest harness (sim OR real CSV data)
  optimize_sweep.py       Offline grid-search + walk-forward validation +
                          current-vs-best compare (scored by mean Sharpe)
  export_csv.py           Export/record a price series to per-symbol CSV files
  fetch_data.py           Download REAL historical data (Yahoo) as CSVs
  engine/
    market.py             Geometric random-walk market simulator
    csv_market.py         Historical CSV replay (drop-in for the simulator)
    portfolio.py          Cash, positions, realised/unrealised P&L, exposure
    guardian.py           Real-time per-trade & portfolio risk verdict
    strategy.py           Indicators + the 5 voters + AIStrategy wrapper
    static/
    index.html            WeBull-style dashboard (live candle chart, equity
                          curve, trade blotter, lifetime stats + panels)
  tests/                  Pytest suite (113 tests) for the safety-critical code

--------------------------------------------------------------------------
 API ENDPOINTS
--------------------------------------------------------------------------
  POST /start_day          Start a governed trading session
  POST /end_day            End the session cleanly
  POST /kill_switch        Emergency stop + flatten all positions
  GET  /status             Full system snapshot (used by the dashboard)
  GET  /history/{symbol}   Recent tick history for charting
  GET  /trades             Persisted trade blotter (survives restarts)
  GET  /equity_history     Persisted equity-curve snapshots
  GET  /sessions           Persisted daily session results
  GET  /                   Redirects to the dashboard

--------------------------------------------------------------------------
 TESTING & BACKTESTING
--------------------------------------------------------------------------
Run the test suite (113 tests covering P&L accounting + reconciliation
invariants, governor limits, per-trade stops, take-profit/trailing exits,
short selling, short-side risk-gate symmetry, gross-leverage/margin caps,
heat/correlation caps, drawdown ladder, regime detection, persistence,
CSV replay and the backtester/optimizer):
     PYTHONPATH=. python3 -m pytest

Run a deterministic backtest on simulated data (reproducible via --seed):
     PYTHONPATH=. python3 -m trading_bot.backtest --ticks 1000 --seed 42

Run a backtest on REAL historical data (one <SYMBOL>.csv per symbol with a
'close' column; slashes in futures symbols written as '_', e.g. _ES.csv):
     PYTHONPATH=. python3 -m trading_bot.backtest --csv-dir path/to/csvs

Fetch REAL historical data (free, no API key — Yahoo Finance):
     PYTHONPATH=. python3 -m trading_bot.fetch_data --out data_real --days 700
     PYTHONPATH=. python3 -m trading_bot.backtest --csv-dir data_real

Generate synthetic sample CSVs (template for the real-data format):
     PYTHONPATH=. python3 -m trading_bot.export_csv --out data_csv --bars 1200

*** IMPORTANT: read FINDINGS_REAL_DATA.md ***
The strategy looks profitable on the simulator but is roughly break-even to
slightly negative on REAL daily data, with much larger drawdowns. The $7,000/
day target and $50 stop are RISK GUARDRAILS, not return expectations. See the
findings doc for the full analysis and the prioritised next steps.

Strategy parameter tools (all use the deterministic backtester):
     # full grid search, ranked by mean Sharpe
     PYTHONPATH=. python3 -m trading_bot.optimize_sweep --ticks 800
     # in-sample/out-of-sample overfitting check
     PYTHONPATH=. python3 -m trading_bot.optimize_sweep --walk-forward
     # current shipping config vs. best candidate
     PYTHONPATH=. python3 -m trading_bot.optimize_sweep --compare

--------------------------------------------------------------------------
 PERSISTENCE
--------------------------------------------------------------------------
All trades, daily sessions, the equity curve and the adaptive Hive-Mind
voter weights are stored in a local SQLite database at:
     trading_bot/data/guardian.db
This means trade history, lifetime stats and the optimizer's learning
survive restarts. The persistence layer is fully failure-tolerant: if the
database is unavailable the trading loop keeps running unaffected.
The database is created automatically on first run.

--------------------------------------------------------------------------
 NOTES
--------------------------------------------------------------------------
- This is a PAPER-TRADING / simulation system. The market data is generated
  locally so you can run, demo and develop without any broker or API key.
- To wire in a real broker/data feed later, replace MarketSimulator and add a
  live execution adapter behind portfolio.execute_buy / execute_sell; every
  risk governor above will continue to apply unchanged.
==========================================================================

==========================================================================
 AUTOMATED PROTECTION, HARD LIMITS & ALERTS  (set-it-and-forget-it)
==========================================================================
You press "START TRADING DAY". Everything else is automatic.

HARD DAILY LOSS LIMIT (non-negotiable):
  * The configured MAX_DAILY_LOSS is an absolute ceiling.
  * A safety buffer (DAILY_LOSS_SAFETY_BUFFER, default 0.90) means the system
    halts at 90% of the limit, so slippage on the exit orders can't push the
    realised loss past your maximum.
  * The INSTANT the limit is reached, ALL positions are auto-flattened and the
    day ends. You are moved to cash and cannot lose more that day.
  * A proactive guard also refuses to OPEN new positions when too little loss
    budget remains.
  * The limit ONLY changes when YOU change it:
        POST /set_loss_limit?max_loss=250
        POST /set_limits?max_loss=250&max_profit=8000&per_trade_stop=60
    Nothing in the system ever alters it automatically.

DAILY PROFIT TARGET:
  * On reaching MAX_DAILY_PROFIT the day is locked in (positions flattened) so
    gains are protected.

ALERTS — you're always in the loop:
  * In-app feed (dashboard "Alerts & Activity" panel; also GET /notifications).
  * Optional EMAIL for important events (day start, approaching limits, loss/
    profit limit hit & day-ended, kill switch, limit changes).
  * Enable email (optional):
        export GUARDIAN_EMAIL_ENABLED=1
        export GUARDIAN_SMTP_HOST=smtp.gmail.com
        export GUARDIAN_SMTP_PORT=587
        export GUARDIAN_SMTP_USER=you@gmail.com
        export GUARDIAN_SMTP_PASS=your_app_password   # Gmail "app password"
        export GUARDIAN_EMAIL_TO=you@gmail.com
    Email is fully optional and failure-tolerant: if it's off or misconfigured,
    trading is never affected and all alerts still appear in-app.

HONEST NOTE ON EXPECTATIONS:
  The system GUARANTEES your loss ceiling and automates all protection. It does
  NOT (and no honest system can) guarantee a win rate or that most days are
  green. What it guarantees is that losses are strictly capped and you're always
  informed. See FINDINGS_REAL_DATA.md for the validated, realistic performance.
==========================================================================

==========================================================================
 AUTO-EXECUTING TREND ALLOCATOR  (the validated, hands-off edge)
==========================================================================
The trend allocator that beat buy-and-hold out-of-sample can now run itself.

  * Turn it on:   POST /allocator/enable   (or the "▶ Auto-Run" dashboard button)
  * Pause it:     POST /allocator/disable  ("⏸ Pause")
  * Go to cash:   POST /allocator/flatten  ("💵 Cash")
  * Live status:  GET  /allocator/live

When enabled it:
  - Invests immediately in the leading uptrending assets (inverse-vol weighted).
  - Rebalances automatically on a weekly cadence.
  - Moves entirely to CASH when the market falls below its long-term trend
    (the crash filter), and re-invests when the uptrend resumes.
  - Sends an alert on every rebalance and every risk-on / risk-off flip.

It runs on daily bars from the CSV history in ALLOCATOR_DATA_DIR (default
data_focus). Refresh that data anytime with:
     PYTHONPATH=. python3 -m trading_bot.fetch_data --out data_focus --days 3650

NOTE: This is PAPER trading on real historical/own price data. It is a separate,
long-horizon engine from the intraday Hive-Mind bot; you can run either or both.

==========================================================================
 CONFIRM YOUR EMAIL ALERTS WORK  (before a live session)
==========================================================================
  * Click "✉️ Send Test Email" on the dashboard, or POST /test_email
  * It sends ONE real email and tells you exactly success/failure + why.
  * If email isn't configured it says so clearly (and still logs in-app).

Enable email first (optional) via the env vars in the section above, then
restart the app and click the test button. Your password is never exposed by
any endpoint.
==========================================================================

==========================================================================
 EASIEST WAY TO START  (no typing!)
==========================================================================
  * On Mac/Linux:  double-click  START_HERE_Mac.command
  * On Windows:    double-click  START_HERE_Windows.bat

It installs what's needed, starts the system, and opens your browser to
the dashboard automatically (http://localhost:8000).

To STOP everything: just close that window (or press Ctrl+C in it).

(The very first time on Mac, if double-click is blocked: right-click the
 file -> Open -> Open. You only do this once.)

==========================================================================
 ADD YOUR OWN SYMBOLS TO WATCH/TRADE
==========================================================================
The Hive-Mind trades from a watchlist. You can add ANY symbol you like:

  * On the dashboard: use the "➕ Add Your Own Symbol" box (left side),
    type a symbol and click "Add to Watchlist".
  * Futures use a leading "/". Handy examples already known to the system
    (they get realistic starting prices automatically):
        /GC  Gold        /MGC Micro Gold
        /CL  Crude Oil   /MCL Micro Crude Oil
        /ZC  Corn        /ZW  Wheat        /ZS Soybeans
        /LE  Live Cattle /HE  Lean Hogs (Livestock)  /GF Feeder Cattle
        /SI  Silver      /NG  Natural Gas
        /ES /MES /NQ /MNQ /RTY /YM  (index futures)
  * Any other symbol works too; it just starts at a default price you can set.

You can also remove a symbol anytime (its open position is closed first).
The Hive-Mind decides WHICH watchlist symbols to actually trade — you decide
WHAT is on the watchlist and WHEN to run.

==========================================================================
 REAL BROKER:  ALPACA  (Simulator -> Paper -> Live)
==========================================================================
The system now supports a REAL broker (Alpaca) with three modes you pick from
the dropdown at the top of the dashboard:

  🧪 SIMULATOR        fake prices, fake money       (default; always safe)
  📝 ALPACA PAPER     REAL market prices, FAKE money (recommended next step)
  🔴 ALPACA LIVE      REAL money                     (deliberately hard-gated)

HOW TO CONNECT ALPACA (free):
  1. Make a free account at  https://app.alpaca.markets
  2. Use the "Paper Trading" account, open the "API Keys" panel, generate a
     key + secret.
  3. Put them in your environment BEFORE starting the app:
        export ALPACA_API_KEY_ID=your_key_here
        export ALPACA_API_SECRET_KEY=your_secret_here
     (Windows:  set ALPACA_API_KEY_ID=your_key_here   etc.)
  4. Start the app and choose "ALPACA PAPER" from the dropdown.
     -> You're now trading with REAL prices and FAKE money. Nothing at risk.

GOING LIVE (real money) — extra safety gate, on purpose:
  * Only do this after you're happy with paper results.
  * You must ALSO set:   export GUARDIAN_ALLOW_LIVE=1
    ...and use your LIVE Alpaca keys. Without that flag, LIVE is refused.
  * The dashboard turns red and shows "🔴 LIVE", and asks you to confirm.
  * All your protections (hard daily loss limit, kill switch, alerts) apply to
    real money exactly as they do in paper/sim.

NOTES (honest):
  * Keys are read from environment variables only — never written to disk or
    exposed by any endpoint.
  * You cannot switch modes while a session is running (stop first) so nothing
    is left half-done across two accounts.
  * Alpaca trades U.S. stocks/ETFs & crypto. (Futures like /CL, /GC are
    supported in the simulator for practice but are not Alpaca-tradable.)

==========================================================================
 EASIEST WAY TO CONNECT ALPACA  (no terminal needed!)
==========================================================================
You can now paste your keys right on the dashboard:

  1. Get FREE keys:
        - Go to  https://alpaca.markets  and Sign Up (free).
        - Log in at  https://app.alpaca.markets
        - Switch to the "Paper" (practice) account.
        - Open the "API Keys" panel -> "Generate New Keys".
        - Copy the Key ID and the Secret Key (secret is shown ONCE!).
  2. On the dashboard, find the "🔑 Broker Setup (Alpaca)" box (top-left).
  3. Paste the Key ID and Secret Key, click "💾 Save Keys".
  4. Click "🔌 Test Connection". You should see, e.g.:
        ✅ Connected to your Alpaca paper account PA1234 — buying power $100,000.00
  5. Pick "📝 ALPACA PAPER" from the mode dropdown at the top. Done!

(Keys pasted this way are kept in memory only for the session and are never
 written to disk. For a permanent setup, use the environment-variable method
 described above.)

==========================================================================
 EASIEST WAY TO TURN ON EMAIL ALERTS  (no terminal needed!)
==========================================================================
  1. On the dashboard, open the "🔔 Alerts & Activity" panel.
  2. Click "📧 Set up email alerts".
  3. Enter your email address and password, click "Save & Enable Email".
     - The mail server is auto-detected for Gmail, Outlook/Hotmail, Yahoo,
       iCloud, and AOL. (Other providers: enter the SMTP host manually.)
  4. Click "✉️ Send Test Email" to confirm it works.

IMPORTANT for Gmail / Yahoo / iCloud users:
  Use an "App Password", NOT your normal login password. Your email provider's
  security settings can generate one (search "<provider> app password").
  Normal passwords are blocked by these providers for apps.

Credentials are kept in memory for the session only and are never written to
disk or shown by any screen.
