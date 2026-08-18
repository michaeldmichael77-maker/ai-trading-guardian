import pandas as pd
import pandas_ta as ta

class RegimeDetector:
    """
    Analyzes market volatility and trend strength to protect 
    the AI from trading in 'Choppy' or 'No-Win' zones.
    """
    def __init__(self, adx_period=14):
        self.adx_period = adx_period

    def analyze(self, price_history):
        """
        Returns a dictionary with Regime_Type and metadata.
        """
        if len(price_history) < 30:
            return {
                "type": "UNKNOWN",
                "score": 0.0,
                "color": "#707a8a",
                "description": "Awaiting data..."
            }

        # Convert to DataFrame
        df = pd.DataFrame(price_history, columns=['close'])
        
        # Calculate 'Chop Index'
        # Higher = more choppy, Lower = more trending
        # Using a fallback if high/low aren't available
        chop = ta.chop(df['close'], df['close'], df['close'], length=self.adx_period)
        current_chop = chop.iloc[-1] if (chop is not None and not chop.empty) else 50.0

        if current_chop < 45:
            regime = "TRENDING"
            status_color = "#00ff88" # Green
        elif current_chop > 55:
            regime = "CHOPPY"
            status_color = "#ff3e3e" # Red
        else:
            regime = "NEUTRAL"
            status_color = "#707a8a" # Dim

        return {
            "type": regime,
            "score": round(current_chop, 2),
            "color": status_color,
            "description": "Trend detected" if regime == "TRENDING" else "Avoiding noise"
        }
