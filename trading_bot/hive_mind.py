"""The Hive-Mind.

A weighted ensemble that aggregates every technical voter, then modulates the
result using market regime, multi-timeframe alignment and sentiment.  It keeps
adaptive weights per voter (nudged by the AutoOptimizer based on realised
performance) so the swarm gets smarter over time.
"""

from trading_bot.engine.strategy import (
    MovingAverageVoter, RSIVoter, MACDVoter, BollingerVoter, MomentumVoter,
)


# Which voters to trust more in which regime.
REGIME_BIAS = {
    "TRENDING_UP":   {"MA_Cross": 1.3, "MACD": 1.2, "Momentum": 1.3, "RSI": 0.8, "Bollinger": 0.7},
    "TRENDING_DOWN": {"MA_Cross": 1.3, "MACD": 1.2, "Momentum": 1.3, "RSI": 0.8, "Bollinger": 0.7},
    "RANGING":       {"RSI": 1.4, "Bollinger": 1.4, "MA_Cross": 0.7, "MACD": 0.8, "Momentum": 0.7},
    "VOLATILE":      {"RSI": 1.1, "Bollinger": 1.2, "MA_Cross": 0.8, "MACD": 0.9, "Momentum": 0.9},
    "UNKNOWN":       {},
}


class HiveMind:
    def __init__(self):
        self.voters = [
            MovingAverageVoter(),
            RSIVoter(),
            MACDVoter(),
            BollingerVoter(),
            MomentumVoter(),
        ]
        # Adaptive base weights (tuned by AutoOptimizer).
        self.weights = {v.name: 1.0 for v in self.voters}
        self.last_decision = {}

    def set_weights(self, weights):
        for k, val in weights.items():
            if k in self.weights:
                self.weights[k] = val

    def decide(self, prices, regime="UNKNOWN", mtf=None, sentiment=0.0):
        """Return a rich decision dict the trade engine can act on."""
        if len(prices) < 30:
            return {
                "signal": "HOLD", "confidence": 0.5,
                "reason": "Hive-Mind warming up", "votes": [], "score": 0.0,
            }

        bias = REGIME_BIAS.get(regime, {})
        buy_score = 0.0
        sell_score = 0.0
        total_weight = 0.0
        vote_details = []

        for voter in self.voters:
            signal, reason, conf = voter.vote(prices)
            w = self.weights[voter.name] * bias.get(voter.name, 1.0)
            total_weight += w
            contribution = conf * w
            if signal == "BUY":
                buy_score += contribution
            elif signal == "SELL":
                sell_score += contribution
            vote_details.append(
                {"voter": voter.name, "signal": signal,
                 "confidence": round(conf, 2), "reason": reason}
            )

        if total_weight == 0:
            total_weight = 1.0

        net = (buy_score - sell_score) / total_weight  # [-1, 1]-ish

        # Sentiment tilt (soft).
        net += sentiment * 0.10

        # Multi-timeframe gate: misalignment dampens conviction.
        mtf_factor = 1.0
        if mtf is not None:
            if mtf.get("aligned"):
                mtf_factor = 1.15
            elif mtf.get("direction") == "MIXED":
                mtf_factor = 0.7
        net *= mtf_factor

        signal = "HOLD"
        if net > 0.12:
            signal = "BUY"
        elif net < -0.12:
            signal = "SELL"

        confidence = min(0.98, 0.5 + abs(net) * 0.9)
        agree = sum(1 for v in vote_details if v["signal"] == signal and signal != "HOLD")

        reason = (
            f"{agree}/{len(self.voters)} agree | regime={regime}"
            f"{' | MTF✓' if mtf and mtf.get('aligned') else ''}"
        )

        decision = {
            "signal": signal,
            "confidence": round(confidence, 3),
            "reason": reason,
            "votes": vote_details,
            "score": round(net, 3),
            "buy_score": round(buy_score, 2),
            "sell_score": round(sell_score, 2),
        }
        self.last_decision = decision
        return decision
