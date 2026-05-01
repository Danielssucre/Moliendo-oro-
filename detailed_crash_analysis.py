import json
import os

log_path = 'logs/basket_theory.jsonl'
if not os.path.exists(log_path):
    print(f"{log_path} not found")
    exit(1)

history = []
with open(log_path, 'r') as f:
    for line in f:
        try:
            data = json.loads(line)
            if 'equity' in data:
                history.append({'time': data.get('time', 'unknown'), 'equity': data['equity'], 'pnl': data.get('pnl', 0)})
        except: continue

if not history:
    print("No history found")
    exit(1)

# Analyze the peak and the descent
peak = -1.0
peak_time = ""
start_equity = history[0]['equity']
current_equity = history[-1]['equity']

print(f"Start Equity: {start_equity}")
print(f"Current Equity: {current_equity}")

for h in history:
    if h['equity'] > peak:
        peak = h['equity']
        peak_time = h['time']

print(f"Peak Equity: {peak} at {peak_time}")

# Find phases
# Phase 1: Growth to peak
# Phase 2: Descent from peak

# To find "Why", I need to correlate the equity drops with specific symbols and strategies.
# I will check logs/trading_*.log for the period of the drops.
# I'll output the top 10 biggest drops in equity from the history.
drops = []
for i in range(1, len(history)):
    diff = history[i]['equity'] - history[i-1]['equity']
    if diff < 0:
        drops.append({'time': history[i]['time'], 'drop': diff, 'equity_before': history[i-1]['equity'], 'equity_after': history[i]['equity']})

drops.sort(key=lambda x: x['drop'])
print("\nTop 10 Biggest Drops:")
for d in drops[:10]:
    print(f"Time: {d['time']} | Drop: {d['drop']:.2f} | {d['equity_before']:.2f} -> {d['equity_after']:.2f}")

# Correlation with signals? I need logs/trading_*.log
