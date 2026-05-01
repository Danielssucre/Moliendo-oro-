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
                history.append({'time': data.get('time', 'unknown'), 'equity': data['equity']})
        except: continue

if not history:
    print("No history found")
    exit(1)

print(f"Total entries: {len(history)}")
print(f"Start Equity: {history[0]['equity']} at {history[0]['time']}")
print(f"End Equity: {history[-1]['equity']} at {history[-1]['time']}")

# Find sudden drops (more than 10%)
for i in range(1, len(history)):
    prev = history[i-1]['equity']
    curr = history[i]['equity']
    if prev > 0:
        drop = (prev - curr) / prev
        if drop > 0.05: # 5% drop in one step
            print(f"⚠️ DROP DETECTED: {prev} -> {curr} ({drop*100:.2f}%) at {history[i]['time']}")
    # Also find large gains
    if prev > 0:
        gain = (curr - prev) / prev
        if gain > 0.05:
            print(f"✨ GAIN DETECTED: {prev} -> {curr} ({gain*100:.2f}%) at {history[i]['time']}")

# Find overall peak
peak = max(h['equity'] for h in history)
peak_time = [h['time'] for h in history if h['equity'] == peak][0]
print(f"\nOverall Peak: {peak} at {peak_time}")
