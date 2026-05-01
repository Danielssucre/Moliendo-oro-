import json
log_path = 'logs/basket_theory.jsonl'
with open(log_path, 'r') as f:
    for line in f:
        try:
            data = json.loads(line)
            if data.get('count', 0) > 10:
                print(f"Time: {data['time']} | Equity: {data['equity']} | Count: {data['count']}")
                # Only report first instances or when count changes
                break
        except: continue

# Find when it went from low count to high count
history = []
with open(log_path, 'r') as f:
    for line in f:
        try:
            data = json.loads(line)
            history.append(data)
        except: continue

print("\nCount Change Log:")
prev_count = -1
for h in history:
    if h.get('count') != prev_count:
        print(f"Time: {h['time']} | Equity: {h['equity']} | Count: {h['count']}")
        prev_count = h.get('count')
