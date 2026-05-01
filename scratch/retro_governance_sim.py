import json
import os
from datetime import datetime

# Path to the ledger
LEDGER_PATH = "logs/history/master_ledger.json"

def simulate_governance():
    if not os.path.exists(LEDGER_PATH):
        print("Master ledger not found.")
        return

    with open(LEDGER_PATH, "r") as f:
        trades = json.load(f)

    # Filter trades from April 19, 2026
    start_date = datetime(2026, 4, 19)
    relevant_trades = []
    for t in trades:
        try:
            t_time = datetime.strptime(t["time"], "%Y-%m-%d %H:%M:%S")
            if t_time >= start_date:
                relevant_trades.append(t)
        except:
            continue

    # Sorting just in case
    relevant_trades.sort(key=lambda x: x["time"])

    initial_balance = 10000.0
    actual_balance = initial_balance
    sim_balance = initial_balance
    
    current_risk_mult = 1.0
    wins_in_a_row = 0
    
    print(f"{'Time':<20} | {'Actual P/L':<10} | {'Sim P/L':<10} | {'Actual Bal':<10} | {'Sim Bal':<10} | {'Mode'}")
    print("-" * 85)

    for t in relevant_trades:
        profit = t["profit"]
        # In reality, profit is based on some lot size. 
        # We'll assume the relative performance would scale with our risk multiplier.
        # Since I don't know the exact risk % used for each real trade, 
        # I'll normalize it: 
        # Simulated Profit = Real Profit * Simulated_Risk_Multiplier
        # This is a simplification but valid for "scaling" analysis.
        
        # Governance Logic (Simplified)
        mode = "NORMAL"
        
        # 1. Shield Mode (DD > 2%)
        if (sim_balance / initial_balance) < 0.98:
            current_risk_mult = 0.4
            mode = "SHIELD"
        # 2. Growth Mode (Winning Streak - Z-Score proxy: Win after Win)
        elif wins_in_a_row >= 1:
            current_risk_mult = 1.5
            mode = "GROWTH"
        else:
            current_risk_mult = 1.0
            mode = "NORMAL"

        sim_profit = profit * current_risk_mult
        
        actual_balance += profit
        sim_balance += sim_profit
        
        # Update streak
        if profit > 0:
            wins_in_a_row += 1
        else:
            wins_in_a_row = 0

        print(f"{t['time']:<20} | {profit:>10.2f} | {sim_profit:>10.2f} | {actual_balance:>10.2f} | {sim_balance:>10.2f} | {mode}")

    print("-" * 85)
    print(f"FINAL ACTUAL BALANCE: {actual_balance:.2f} (DD: {(1 - actual_balance/initial_balance)*100:.2f}%)")
    print(f"FINAL SIMULATED BALANCE: {sim_balance:.2f} (DD: {(1 - sim_balance/initial_balance)*100:.2f}%)")
    print(f"ALPHA PRESERVATION: {(sim_balance - actual_balance):.2f}")

if __name__ == "__main__":
    simulate_governance()
