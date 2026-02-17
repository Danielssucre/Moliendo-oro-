#!/usr/bin/env python3
"""
RL Infinite Trailing Benchmark
Compares the RL Agent policy against the Step Trailing 0.5R baseline.
"""
import os
import json
import numpy as np
import torch
import torch.nn as nn

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
        # Update trailing
        num_steps = int((bar['max_r'] - 1.3) // step_size_r) if bar['max_r'] >= 1.3 else 0
        sl_r = max(sl_r, num_steps * step_size_r)
    return history[-1]['current_r']

def simulate_rl_policy(history, q_net):
    sl_r = 0.0
    for i, bar in enumerate(history):
        # State: [current_r, max_r, ema_slope, vol, atr_norm, current_sl_r]
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
            
        # Check SL hit
        if bar['current_r'] <= sl_r:
            return sl_r
            
    return history[-1]['current_r']

def run_benchmark():
    if not os.path.exists(DATA_PATH) or not os.path.exists(MODEL_PATH):
        print("❌ Missing data or models")
        return
        
    with open(DATA_PATH, 'r') as f:
        trajectories = json.load(f)
        
    # Split: Only test on the last 20%
    split_idx = int(len(trajectories) * 0.8)
    test_trajectories = trajectories[split_idx:]
    
    q_net = QNetwork(6, 3)
    q_net.load_state_dict(torch.load(MODEL_PATH))
    q_net.eval()
    
    results = {
        "Baseline (Fixed 3.1R)": 0.0,
        "Step Trailing (0.5R)": 0.0,
        "RL Agent Policy": 0.0
    }
    
    for traj in test_trajectories:
        history = traj['history']
        
        # 1. Fixed 3.1R
        # Find if max_r ever hits 3.1
        max_r_reached = max([h['max_r'] for h in history])
        results["Baseline (Fixed 3.1R)"] += 1.8 if max_r_reached >= 3.1 else 0.0
        
        # 2. Step 0.5R
        results["Step Trailing (0.5R)"] += simulate_step_trailing(history, 0.5)
        
        # 3. RL Policy
        results["RL Agent Policy"] += simulate_rl_policy(history, q_net)
        
    print("\n" + "="*60)
    print("🤖 REINFORCEMENT LEARNING BENCHMARK")
    print("="*60)
    print(f"Test Trajectories: {len(test_trajectories)}")
    print("-" * 60)
    
    for name, total_r in results.items():
        avg_r = total_r / len(test_trajectories)
        print(f"{name:<25} | Total R: {total_r:>10.2f} | Avg: {avg_r:>5.2f}")
    
    print("-" * 60)
    alpha = results["RL Agent Policy"] - results["Step Trailing (0.5R)"]
    print(f"🎯 RL Incremental Alpha: {alpha:>+10.2f} R")
    print("="*60)

if __name__ == "__main__":
    run_benchmark()
