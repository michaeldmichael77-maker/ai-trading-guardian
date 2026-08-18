import random
import alpaca_trade_api as tradeapi

class MarketSimulator:
    """Simulates a real-time price feed for testing."""
    def __init__(self, start_price=50000.0):
        self.current_price = start_price

    def get_price(self):
        change_percent = random.uniform(-0.001, 0.001)
        self.current_price *= (1 + change_percent)
        return round(self.current_price, 2)

class AlpacaConnector:
    """Connects to the real Alpaca Market API."""
    def __init__(self, api_key, secret_key, base_url="https://paper-api.alpaca.markets"):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        try:
            self.api = tradeapi.REST(api_key, secret_key, base_url, api_version='v2')
            print("Successfully connected to Alpaca API")
        except Exception as e:
            print(f"Alpaca Connection Error: {e}")
            self.api = None

    def get_price(self, symbol="BTC/USD"):
        if not self.api:
            return None
        try:
            alpaca_symbol = symbol.replace("/", "")
            trade = self.api.get_latest_trade(alpaca_symbol)
            return round(trade.price, 2)
        except Exception as e:
            print(f"Error fetching price: {e}")
            return None