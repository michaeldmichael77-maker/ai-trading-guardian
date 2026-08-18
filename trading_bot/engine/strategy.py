import pandas as pd
import pandas_ta as ta

class AIStrategy:
    """Advanced Brain using RSI, EMA, MACD, and Bollinger Bands."""
    def __init__(self, window_size=50):
        self.window_size = window_size

    def analyze(self, price_history):
        if len(price_history) < self.window_size:
            return "HOLD", "Collecting data..."

        df = pd.DataFrame(price_history, columns=['close'])

        rsi = ta.rsi(df['close'], length=14)
        current_rsi = rsi.iloc[-1] if rsi is not None else 50

        ema_20 = ta.ema(df['close'], length=20)
        current_ema = ema_20.iloc[-1] if ema_20 is not None else 0
        current_price = price_history[-1]

        macd = ta.macd(df['close'])
        if macd is not None:
            current_macd = macd['MACD_12_26_9'].iloc[-1]
            signal_line = macd['MACDs_12_26_9'].iloc[-1]
            macd_bullish = current_macd > signal_line
        else:
            macd_bullish = False

        bbands = ta.bbands(df['close'], length=20, std=2)
        if bbands is not None:
            lower_band = bbands['BBL_20_2.0'].iloc[-1]
            upper_band = bbands['BBU_20_2.0'].iloc[-1]
            at_lower_band = current_price <= lower_band
            at_upper_band = current_price >= upper_band
        else:
            at_lower_band = at_upper_band = False

        if (current_rsi < 35 or at_lower_band) and current_price > current_ema and macd_bullish:
            return "BUY", f"Bullish Convergence: RSI({current_rsi:.1f}) + MACD Bullish + BB Lower"

        if current_rsi > 65 or at_upper_band:
            return "SELL", f"Bearish Extremes: RSI({current_rsi:.1f}) + BB Upper"

        if not macd_bullish and current_price < current_ema:
            return "SELL", "Trend Reversal: MACD Bearish + Below EMA"

        return "HOLD", f"RSI: {current_rsi:.1f} | MACD: {'Bull' if macd_bullish else 'Bear'} | BB: Normal"