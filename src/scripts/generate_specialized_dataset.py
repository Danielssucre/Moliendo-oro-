
import json
import pandas as pd
import re
import os
import sys
import subprocess
from datetime import datetime, timedelta
from siliconmetatrader5 import MetaTrader5

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def extract_val(text, pattern):
    match = re.search(pattern, text)
    if match:
        val_str = match.group(1).rstrip('.')
        try:
            return float(val_str)
        except ValueError:
            return None
    return None

def generate_dataset():
    mt5 = MetaTrader5(port=8001)
    if not mt5.initialize():
        print("MT5 Init Failed")
        return

    jsonl_path = "logs/operations.jsonl"
    if not os.path.exists(jsonl_path):
        print(f"File not found: {jsonl_path}")
        return

    # Use tail to get recent signals
    print(f"Reading recent signals from {jsonl_path}...")
    try:
        # Get last 40,000 lines to ensure diversity
        lines = subprocess.check_output(["tail", "-n", "40000", jsonl_path]).decode("utf-8").split("\n")
        lines.reverse() # Most recent first
    except Exception as e:
        print(f"Tail failed: {e}")
        return

    records = []
    count = 0
    max_to_collect = 2000
    signal_types_found = 0

    for line in lines:
        line = line.strip()
        if not line: continue
        
        try:
            entry = json.loads(line)
            if entry.get("type") != "signal_generated":
                continue
            
            signal_types_found += 1
            data = entry["data"]
            symbol = data["pair"]
            direction = data["direction"]
            timestamp_str = data["timestamp"]
            
            try:
                entry_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                entry_time = datetime.fromisoformat(timestamp_str)
            
            entry_price = data["entry_price"]
            sl = data["stop_loss"]
            tp = data["take_profit"]
            prob = data["probability"]
            
            # Extract indicators
            adx = extract_val(data["trend_analysis"], r"ADX=([\d\.]+)")
            rsi_str = " ".join(data["indicator_confirmations"])
            rsi = extract_val(rsi_str, r"RSI.*?\(([\d\.]+)\)")
            vol = data.get("atr_value", 0)
            
            if adx is None or rsi is None:
                continue

            # Query MT5 for outcome
            start_dt = entry_time
            end_dt = entry_time + timedelta(hours=24)
            rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, start_dt, end_dt)
            
            if rates is None or len(rates) == 0:
                continue
            
            outcome_r = -1.0
            risk = abs(entry_price - sl)
            if risk == 0: continue
            
            found_outcome = False
            for bar in rates:
                bar_time = datetime.fromtimestamp(bar['time'])
                if bar_time < entry_time:
                    continue
                
                if direction == "BUY":
                    if bar['low'] <= sl:
                        outcome_r = -1.0
                        found_outcome = True
                        break
                    if bar['high'] >= tp:
                        outcome_r = (tp - entry_price) / risk
                        found_outcome = True
                        break
                else: # SELL
                    if bar['high'] >= sl:
                        outcome_r = -1.0
                        found_outcome = True
                        break
                    if bar['low'] <= tp:
                        outcome_r = (entry_price - tp) / risk
                        found_outcome = True
                        break
            
            if not found_outcome:
                last_price = rates[-1]['close']
                if direction == "BUY":
                    outcome_r = (last_price - entry_price) / risk
                else:
                    outcome_r = (entry_price - last_price) / risk

            records.append({
                "symbol": symbol,
                "prob": prob,
                "adx": adx,
                "rsi": rsi,
                "vol": vol,
                "outcome_r": outcome_r
            })
            
            count += 1
            if count % 100 == 0:
                print(f"Collected {count} valid signals...")
                # Incremental save
                df_tmp = pd.DataFrame(records)
                df_tmp.to_csv("data/research/risk_specialized_dataset.csv", index=False)
            
            if count >= max_to_collect:
                break

        except Exception as e:
            continue

    df = pd.DataFrame(records)
    output_path = "data/research/risk_specialized_dataset.csv"
    os.makedirs("data/research", exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Dataset generated with {len(df)} records.")
    mt5.shutdown()

if __name__ == "__main__":
    generate_dataset()
