import os

def upgrade_api():
    path = 'trading_bot/api.py'
    with open(path, 'r') as f:
        content = f.read()
    
    # Speed Fix: Parallel Processing
    old_loop = """                        for symbol in config.SYMBOLS:
                            process_symbol(symbol)"""
    
    new_loop = """                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor(max_workers=len(config.SYMBOLS)) as executor:
                            executor.map(process_symbol, config.SYMBOLS)"""
    
    if old_loop in content:
        content = content.replace(old_loop, new_loop)
        print("API Speed: Concurrent executor installed.")
    
    with open(path, 'w') as f:
        f.write(content)

def upgrade_hive_mind():
    path = 'trading_bot/hive_mind.py'
    with open(path, 'r') as f:
        content = f.read()
    
    # Intelligence Fix: Consensus thresholding
    target = "net = (buy_score - sell_score) / total_weight  # [-1, 1]-ish"
    upgrade = """
        # --- INTELLIGENCE UPGRADE: Consensus Thresholding (V34) ---
        agree_count = sum(1 for v in vote_details if v["signal"] == signal and signal != "HOLD")
        agreement_ratio = agree_count / len(self.voters)
        min_consensus = 0.8 if regime in ("VOLATILE", "CHOPPY") else 0.6
        if signal != "HOLD" and agreement_ratio < min_consensus:
            signal = "HOLD"
            reason += f" (Failed Consensus: {agree_count}/{len(self.voters)})"
"""
    if target in content and "Consensus Thresholding" not in content:
        content = content.replace(target, target + upgrade)
        print("Hive-Mind: Consensus gating installed.")
        
    with open(path, 'w') as f:
        f.write(content)

upgrade_api()
upgrade_hive_mind()
