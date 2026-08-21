import os
path = 'trading_bot/api.py'
with open(path, 'r') as f:
    content = f.read()

# Replace the loop with parallel execution
old_loop = """                        for symbol in config.SYMBOLS:
                            process_symbol(symbol)"""
new_loop = """                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor(max_workers=len(config.SYMBOLS)) as executor:
                            executor.map(process_symbol, config.SYMBOLS)"""
if old_loop in content:
    content = content.replace(old_loop, new_loop)
    print("API Speed Upgrade: Success")

with open(path, 'w') as f:
    f.write(content)
