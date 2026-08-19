import os

def upgrade_api():
    filepath = 'trading_bot/api.py'
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Surgical Speed Upgrade: Replace the serial loop with a parallel one
    # Note the precise indentation (24 spaces for the loop body)
    old_loop = """                        for symbol in config.SYMBOLS:
                            process_symbol(symbol)"""
    
    new_loop = """                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            executor.map(process_symbol, config.SYMBOLS)"""
    
    if old_loop in content:
        content = content.replace(old_loop, new_loop)
        print("API Speed Upgrade: Applied.")
    else:
        print("API Speed Upgrade: FAILED (Pattern not found).")
        
    with open(filepath, 'w') as f:
        f.write(content)

def upgrade_hive_mind():
    filepath = 'trading_bot/hive_mind.py'
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Surgical Intelligence Upgrade: Add consensus gating
    target = "net = (buy_score - sell_score) / total_weight  # [-1, 1]-ish"
    
    consensus_logic = """
        # --- INTELLIGENCE UPGRADE: Consensus Thresholding (V27) ---
        agree_count = sum(1 for v in vote_details if v["signal"] == signal and signal != "HOLD")
        agreement_ratio = agree_count / len(self.voters)
        min_consensus = 0.8 if regime in ("VOLATILE", "CHOPPY") else 0.6
        
        if signal != "HOLD" and agreement_ratio < min_consensus:
            signal = "HOLD"
            reason += f" (Consensus Failed: {agree_count}/{len(self.voters)})"
"""
    
    if target in content and "Consensus Thresholding" not in content:
        content = content.replace(target, target + consensus_logic)
        print("Hive-Mind Intelligence Upgrade: Applied.")
    else:
        print("Hive-Mind Intelligence Upgrade: FAILED or already applied.")
        
    with open(filepath, 'w') as f:
        f.write(content)

upgrade_api()
upgrade_hive_mind()
