import os

def run():
    # Upgrade api.py
    api_path = 'trading_bot/api.py'
    if os.path.exists(api_path):
        with open(api_path, 'r') as f:
            lines = f.readlines()
        
        new_lines = []
        found = False
        for line in lines:
            if 'for symbol in config.SYMBOLS:' in line and not found:
                new_lines.append('                        import concurrent.futures\n')
                new_lines.append('                        with concurrent.futures.ThreadPoolExecutor(max_workers=len(config.SYMBOLS)) as executor:\n')
                new_lines.append('                            executor.map(process_symbol, config.SYMBOLS)\n')
                found = True
            elif 'process_symbol(symbol)' in line and found:
                continue
            else:
                new_lines.append(line)
        
        with open(api_path, 'w') as f:
            f.writelines(new_lines)
        print("API Upgrade complete.")

    # Upgrade hive_mind.py
    hive_path = 'trading_bot/hive_mind.py'
    if os.path.exists(hive_path):
        with open(hive_path, 'r') as f:
            content = f.read()
        target = "net = (buy_score - sell_score) / total_weight  # [-1, 1]-ish"
        if target in content and "Consensus Thresholding" not in content:
            upgrade = "\n        # Consensus Intelligence Upgrade (V36)\n        agree_count = sum(1 for v in vote_details if v['signal'] == signal and signal != 'HOLD')\n        agreement_ratio = agree_count / len(self.voters)\n        min_consensus = 0.8 if regime in ('VOLATILE', 'CHOPPY') else 0.6\n        if signal != 'HOLD' and agreement_ratio < min_consensus:\n            signal = 'HOLD'\n            reason += f' (Consensus Failed: {agree_count}/{len(self.voters)})'"
            content = content.replace(target, target + upgrade)
            with open(hive_path, 'w') as f:
                f.write(content)
            print("Hive-Mind Upgrade complete.")

run()
