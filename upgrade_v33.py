import os

def fix_api():
    path = 'trading_bot/api.py'
    with open(path, 'r') as f:
        content = f.read()
    
    # Surgical Speed: Concurrent symbols (using your actual loop pattern)
    old = "                        for symbol in config.SYMBOLS:\n                            process_symbol(symbol)"
    new = "                        import concurrent.futures\n                        with concurrent.futures.ThreadPoolExecutor() as executor:\n                            executor.map(process_symbol, config.SYMBOLS)"
    
    if old in content:
        content = content.replace(old, new)
        print("Speed logic injected.")
    
    with open(path, 'w') as f:
        f.write(content)

def fix_brain():
    path = 'trading_bot/hive_mind.py'
    with open(path, 'r') as f:
        content = f.read()
    
    target = "net = (buy_score - sell_score) / total_weight  # [-1, 1]-ish"
    upgrade = """
        # Consensus Intelligence (V33)
        agree_count = sum(1 for v in vote_details if v["signal"] == signal and signal != "HOLD")
        agreement_ratio = agree_count / len(self.voters)
        min_consensus = 0.8 if regime in ("VOLATILE", "CHOPPY") else 0.6
        if signal != "HOLD" and agreement_ratio < min_consensus:
            signal = "HOLD"
            reason += f" (Consensus Failed: {agree_count}/{len(self.voters)})"
"""
    if target in content:
        content = content.replace(target, target + upgrade)
        print("Intelligence logic injected.")
    
    with open(path, 'w') as f:
        f.write(content)

fix_api()
fix_brain()
