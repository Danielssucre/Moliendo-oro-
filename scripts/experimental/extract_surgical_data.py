import re
import os
import pandas as pd
import sys

# Usage: python3 extract.py [logfile]
logfile = sys.argv[1] if len(sys.argv) > 1 else "temp_log.txt"

def extract():
    rows = []
    curr_ml = None
    curr_posterior = 0.5
    
    with open(logfile, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            # ML Risk
            # ✅ [5/7] ML PASSED: BTCUSD Risk=0.50 | Confidence=1.0x
            ml_m = re.search(r"ML PASSED: \w+ Risk=([\d\.]+)", line)
            if ml_m:
                curr_ml = 1.0 - float(ml_m.group(1))
            
            # Bayes
            # ├─ Posterior P(Bullish|E): 0.5833
            # or Posterior=0.5833
            b_m = re.search(r"Posterior P\(Bullish\|E\): ([\d\.]+)", line)
            if not b_m:
                b_m = re.search(r"Posterior=([\d\.]+)", line)
            if b_m:
                curr_posterior = float(b_m.group(1))
            
            # Result / Execution
            # DYNAMIC RISK: 0.280% | Trigger: BTCUSD BUY
            if "DYNAMIC RISK" in line and curr_ml is not None:
                pair_m = re.search(r"Trigger: (\w+)", line)
                pair = pair_m.group(1) if pair_m else "UNK"
                rows.append({
                    'prob_rf': curr_ml,
                    'posterior': curr_posterior,
                    'pair': pair,
                    'result': 'PENDING', # Results are hard to pair in real-time logs
                    'rr': 1.5
                })
                # Reset
                curr_ml = None
                curr_posterior = 0.5

    df = pd.DataFrame(rows)
    if not df.empty:
        print(df.tail(20).to_markdown())
    else:
        print("No paired data found in the provided logs.")

if __name__ == "__main__":
    extract()
