TradingApp_Full - AI Trading Guardian (Full Version)

This is a complete automated trading system with the Hive-Mind.

HOW TO RUN:

1. Open Terminal

2. Go to the project folder:
   cd ~/Desktop/TradingApp_Full

3. Install requirements:
   pip3 install --user -r requirements.txt

4. Start the app:
   PYTHONPATH=. python3 trading_bot/main.py

5. Open your browser and go to:
   http://localhost:8000/static/index.html

6. Click "START TRADING DAY" to begin.

The system will automatically:
- Analyze the markets
- Execute trades when signals are strong
- Respect $50 stop-loss per trade
- Stop at $7,000 profit or $175 loss
- Shut down at the end of the day

Press the red "KILL SWITCH" button anytime to stop immediately.