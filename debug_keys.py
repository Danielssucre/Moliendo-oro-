import json
all_keys = set()
with open('logs/operations.jsonl', 'r') as f:
    for i, line in enumerate(f):
        try:
            data = json.loads(line)
            all_keys.update(data.keys())
            if 'data' in data:
                all_keys.update([f"data.{k}" for k in data['data'].keys()])
        except: continue
        if i > 1000: break
print(all_keys)
