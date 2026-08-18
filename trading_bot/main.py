import uvicorn
from trading_bot.api import app

if __name__ == "__main__":
    print("Launching AI Trading Guardian Dashboard...")
    print("Access your dashboard at: http://localhost:8000/static/index.html")
    uvicorn.run(app, host="0.0.0.0", port=8000)