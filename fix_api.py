import os

filepath = 'trading_bot/api.py'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
skip_mode = False
for line in lines:
    if 'import concurrent.futures' in line:
        new_lines.append('                        import concurrent.futures\n')
        new_lines.append('                        with concurrent.futures.ThreadPoolExecutor() as executor:\n')
        new_lines.append('                            executor.map(process_symbol, config.SYMBOLS)\n')
        skip_mode = True
        continue
    
    if skip_mode:
        if '# --- HARD limit enforcement' in line:
            skip_mode = False
        elif 'prices = bot_state["last_prices"]' in line:
            # We want to keep the lines after the loop
            skip_mode = False
        else:
            continue
            
    if not skip_mode:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)
