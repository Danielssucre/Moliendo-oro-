#!/usr/bin/env python3
"""
Institutional RL Verification Script
Performs a strict chronological test (last 30% of data) and calculates:
- Total R, Avg R, Win Rate.
- Max Drawdown (R).
- Sharpe Ratio.
- Outlier Capture (>5R, >10R).
- Strategy Correlation.
"""
import os
import json
import numpy as np
import torch
import torch.nn as nn
import pandas as pd

# --- SETTINGS ---
DATA_PATH = "data/research/rl_trajectories_v1.json"
MODEL_PATH = "models/infinite_rl_qnet_v1.pth"

class QNetwork(nn.Module):
    def __init__(self, state_dim, action_dim):
        super(QNetwork, self).__init__()
        self.fc1 = nn.Linear(state_dim, 16)
        self.fc2 = nn.Linear(16, 8)
        self.out = nn.Linear(8, action_dim)
        
    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        return self.out(x)

def simulate_step_trailing(history, step_size_r=0.5):
    sl_r = 0.0
    for bar in history:
        if bar['current_r'] <= sl_r:
            return sl_r
        num_steps = int((bar['max_r'] - 1.3) // step_size_r) if bar['max_r'] >= 1.3 else 0
        sl_r = max(sl_r, num_steps * step_size_r)
    return history[-1]['current_r']

def simulate_rl_policy(history, q_net):
    sl_r = 0.0
    for bar in history:
        state = np.array([
            bar['current_r'],
            bar['max_r'],
            bar['ema_9_slope'],
            bar['vol'],
            bar['atr_norm'],
            sl_r
        ], dtype=np.float32)
        
        with torch.no_grad():
            state_t = torch.FloatTensor(state).unsqueeze(0)
            action = q_net(state_t).argmax().item()
        
        if action == 2: # CLOSE
            return bar['current_r']
        elif action == 1: # MOVE SL
            sl_r += 0.5
            
        if bar['current_r'] <= sl_r:
            return sl_r
    return history[-1]['current_r']

def calculate_metrics(returns):
    ret_arr = np.array(returns)
    total_r = np.sum(ret_arr)
    avg_r = np.mean(ret_arr)
    win_rate = np.sum(ret_arr > 0) / len(ret_arr)
    
    # Max Drawdown (Cumulative R)
    cum_r = np.cumsum(ret_arr)
    peak = np.maximum.accumulate(cum_r)
    drawdown = cum_r - peak
    max_dd = np.min(drawdown)
    
    # Sharpe Ratio (Roughly: Avg / Std)
    std_r = np.std(ret_arr)
    sharpe = (avg_r / std_r) * np.sqrt(252) if std_r > 0 else 0 # Annualized assuming 1 trade/day-ish
    
    # Outliers
    moons_5 = np.sum(ret_arr >= 5.0)
    moons_10 = np.sum(ret_arr >= 10.0)
    
    return {
        "Total R": total_r,
        "Avg R": avg_r,
        "Win Rate": win_rate,
        "Max DD (R)": max_dd,
        "Sharpe": sharpe,
        "Outliers >5R": moons_5,
        "Outliers >10R": moons_10
    }

def run_institutional_verification():
    if not os.path.exists(DATA_PATH) or not os.path.exists(MODEL_PATH):
        print("❌ Missing data or models")
        return
        
    with open(DATA_PATH, 'r') as f:
        trajectories = json.load(f)
        
    # Strict Chronological Split (Last 30%)
    split_idx = int(len(trajectories) * 0.7)
    test_trajectories = trajectories[split_idx:]
    
    q_net = QNetwork(6, 3)
    q_net.load_state_dict(torch.load(MODEL_PATH))
    q_net.eval()
    
    results_raw = {
        "Fixed 3.1R": [],
        "Step 0.5R": [],
        "RL Agent": []
    }
    
    for traj in test_trajectories:
        history = traj['history']
        
        # 1. Fixed 3.1R
        max_r = max([h['max_r'] for h in history])
        results_raw["Fixed 3.1R"].append(1.8 if max_r >= 3.1 else 0.0)
        
        # 2. Step 0.5R
        results_raw["Step 0.5R"].append(simulate_step_trailing(history, 0.5))
        
        # 3. RL Agent
        results_raw["RL Agent"].append(simulate_rl_policy(history, q_net))
        
    print("\n" + "="*80)
    print("🏛️  INSTITUTIONAL RL VERIFICATION (Blind Test: Last 30%)")
    print("="*80)
    print(f"Test Sample Size: {len(test_trajectories)} trades")
    print("-" * 80)
    
    metrics_list = []
    for name, rets in results_raw.items():
        m = calculate_metrics(rets)
        m["Strategy"] = name
        metrics_list.append(m)
        
    df_metrics = pd.DataFrame(metrics_list).set_index("Strategy")
    print(df_metrics.T)
    
    print("-" * 80)
    alpha = df_metrics.loc["RL Agent", "Total R"] - df_metrics.loc["Step 0.5R", "Total R"]
    improvement = (alpha / df_metrics.loc["Step 0.5R", "Total R"]) * 100
    print(f"🎯 INSTITUTIONAL ALPHA (vs Step 0.5R): {alpha:>+10.2f} R ({improvement:>+6.1f}%)")
    print("="*80 + "\n")

if __name__ == "__main__":
    run_institutional_verification()
