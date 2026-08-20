"""The Hive-Mind.
A weighted ensemble that aggregates technical voters and enforces Consensus Thresholding.
"""
from trading_bot.engine.strategy import (
    MovingAverageVoter, RSIVoter, MACDVoter, BollingerVoter, MomentumVoter,
)

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
            MovingAverageVoter(), RSIVoter(), MACDVoter(), BollingerVoter(), MomentumVoter(),
        ]
        self.weights = {v.name: 1.0 for v in self.voters}
        self.last_decision = {}

    def set_weights(self, weights):
        for k, val in weights.items():
            if k in self.weights: self.weights[k] = val

    def decide(self, prices, regime="UNKNOWN", mtf=None, sentiment=0.0):
        if len(prices) < 30:
            return {"signal": "HOLD", "confidence": 0.5, "reason": "Hive-Mind warming up", "votes": [], "score": 0.0}

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
            if signal == "BUY": buy_score += contribution
            elif signal == "SELL": sell_score += contribution
            vote_details.append({"voter": voter.name, "signal": signal, "confidence": round(conf, 2), "reason": reason})

        net = (buy_score - sell_score) / (total_weight if total_weight > 0 else 1.0)
        net += sentiment * 0.10

        if mtf is not None:
            if mtf.get("aligned"): net *= 1.15
            elif mtf.get("direction") == "MIXED": net *= 0.7

        signal = "HOLD"
        if net > 0.12: signal = "BUY"
        elif net < -0.12: signal = "SELL"

        # --- INTELLIGENCE UPGRADE: Consensus Thresholding ---
        agree_count = sum(1 for v in vote_details if v["signal"] == signal and signal != "HOLD")
        agreement_ratio = agree_count / len(self.voters)
        min_consensus = 0.8 if regime in ("VOLATILE", "CHOPPY") else 0.6
        
        if signal != "HOLD" and agreement_ratio < min_consensus:
            signal = "HOLD"
            reason = f"Consensus failed ({agree_count}/{len(self.voters)} agree)"
        else:
            reason = f"{agree_count}/{len(self.voters)} agree | regime={regime}"

        decision = {
            "signal": signal, "confidence": round(min(0.98, 0.5 + abs(net) * 0.9), 3),
            "reason": reason, "votes": vote_details, "score": round(net, 3),
        }
        self.last_decision = decision
        return decision
