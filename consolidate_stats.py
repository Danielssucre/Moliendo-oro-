import os
import re
import json
import pandas as pd

log_dir = 'logs'
files = [f for f in os.listdir(log_dir) if f.endswith('.log') or f.endswith('.jsonl')]

stats = []

# Pattern for [LHN-REAL] logs
# 2026-03-24 09:12:45 | INFO | 📊 [LHN-REAL] BTCUSD ALFA_1.5R WIN (R:1.50, MFE:1.60, Session:...)
lhn_pattern = re.compile(r'\[LHN-REAL\]\s+\S+\s+(\w+).*\(R:([\d\.-]+)')

# Pattern for direct variant logs
# ✅ Closed Symbol #Ticket Comment: NEME_3.1R
# Wait, let's just search for the variant tags in the whole line if it contains "Profit" or "R:"

for filename in files:
    path = os.path.join(log_dir, filename)
    if filename.endswith('.jsonl'):
        with open(path, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    # Some jsonl files might have 'profit' and 'comment' or 'tag'
                    if 'profit' in data and ('comment' in data or 'tag' in data):
                        pnl = float(data['profit'])
                        comment = str(data.get('comment', '') or data.get('tag', '')).upper()
                        variant = 'OTHER'
                        for v in ['ALFA', 'NEME', 'EXPL', 'WINNER', 'SNIPER']:
                            if v in comment:
                                variant = v
                                break
                        stats.append({'variant': variant, 'pnl': pnl})
                except: continue
    else:
        with open(path, 'r') as f:
            for line in f:
                match = lhn_pattern.search(line)
                if match:
                    variant_raw = match.group(1).upper()
                    r_val = float(match.group(2))
                    # Fallback to estimate $ from R if $ not present
                    # Let's assume 1R = $1.0 for now if we can't find $
                    # But if we find the word Profit: $X
                    pnl_match = re.search(r'Profit:\s*([\d\.-]+)', line)
                    if pnl_match:
                        pnl = float(pnl_match.group(1))
                    else:
                        pnl = r_val # Using R as a proxy if $ missing
                    
                    variant = 'OTHER'
                    for v in ['ALFA', 'NEME', 'EXPL', 'WINNER', 'SNIPER']:
                        if v in variant_raw:
                            variant = v
                            break
                    stats.append({'variant': variant, 'pnl': pnl})
                
                # Check for "Closed ... Profit: X"
                if 'Closed' in line and 'Profit:' in line:
                    pnl_match = re.search(r'Profit:\s*([\d\.-]+)', line)
                    if pnl_match:
                        pnl = float(pnl_match.group(1))
                        variant = 'OTHER'
                        for v in ['ALFA', 'NEME', 'EXPL', 'WINNER', 'SNIPER']:
                            if v in line.upper():
                                variant = v
                                break
                        stats.append({'variant': variant, 'pnl': pnl})

if not stats:
    print("Zero stats found in logs.")
    exit()

df = pd.DataFrame(stats)
summary = df.groupby('variant')['pnl'].agg(['sum', 'count']).sort_values('sum', ascending=False)
summary.columns = ['Total_PnL', 'Trades']

# Calculate Avg
summary['Avg_PnL'] = summary['Total_PnL'] / summary['Trades']

print("\n--- PERFORMANCE BY BOT VARIANT (Consolidated from Logs) ---")
print(summary)

# Check for historical peak vs current
print(f"\nTotal PnL across all logged events: {df['pnl'].sum():.2f}")
