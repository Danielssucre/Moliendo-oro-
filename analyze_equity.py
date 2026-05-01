import json
import os

log_path = 'logs/operations.jsonl'
if not os.path.exists(log_path):
    print(f"{log_path} not found")
    exit(1)

history = []
with open(log_path, 'r') as f:
    for line in f:
        try:
            data = json.loads(line)
            if 'equity' in data:
                history.append({'time': data.get('time', 'unknown'), 'equity': data['equity'], 'balance': data.get('balance', 0)})
        except:
            continue

# Find large gains and subsequent losses
last_equity = 0
for i in range(len(history)):
    eq = history[i]['equity']
    if i > 0:
        diff = eq - history[i-1]['equity']
        if abs(diff) > 100 or (last_equity > 0 and abs(diff/last_equity) > 0.05):
            print(f"Time: {history[i]['time']} | Equity: {eq} | Change: {diff}")
    last_equity = eq

# Find max equity and current equity
if history:
    max_eq = max(h['equity'] for h in history)
    current_eq = history[-1]['equity']
    print(f"\nMax Equity: {max_eq}")
    print(f"Current Equity: {current_eq}")
    print(f"Total DD from peak: {max_eq - current_eq} ({(max_eq - current_eq)/max_eq*100:.2f}%)")
