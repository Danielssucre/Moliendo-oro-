import json
types = set()
with open('logs/operations.jsonl', 'r') as f:
    for line in f:
        try:
            data = json.loads(line)
            types.add(data['type'])
        except: continue
print(types)
