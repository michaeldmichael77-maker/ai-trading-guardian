path = 'trading_bot/hive_mind.py'
with open(path, 'r') as f:
    content = f.read()

target = "net = (buy_score - sell_score) / total_weight  # [-1, 1]-ish"
consensus_logic = """
        # --- INTELLIGENCE UPGRADE: Consensus Thresholding (V37) ---
        agree_count = sum(1 for v in vote_details if v["signal"] == signal and signal != "HOLD")
        agreement_ratio = agree_count / len(self.voters)
        min_consensus = 0.8 if regime in ("VOLATILE", "CHOPPY") else 0.6
        if signal != "HOLD" and agreement_ratio < min_consensus:
            signal = "HOLD"
            reason += f" (Consensus Failed: {agree_count}/{len(self.voters)})"
"""
if target in content:
    content = content.replace(target, target + consensus_logic)
    print("Hive-Mind Intelligence Upgrade: Success")

with open(path, 'w') as f:
    f.write(content)
