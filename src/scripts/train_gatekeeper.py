#!/usr/bin/env python3
"""
Phase 17: RL Signal Gatekeeper ("The Chooser") v2.0
Trains a DQN agent to ACCEPT (1) or REJECT (0) signals.
Feature Engineering: Added Time (Hour, Day) and Log-Volatility.
"""
import os
import json
import random
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from collections import deque
from datetime import datetime
import logging

# --- CONFIGURATION ---
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(ROOT_DIR, "data/research/rl_trajectories_v1.json")
MODEL_SAVE_PATH = os.path.join(ROOT_DIR, "models/gatekeeper_qnet_v2.pth")
SCALER_SAVE_PATH = os.path.join(ROOT_DIR, "models/gatekeeper_scaler_v2.json")

EPISODES = 3000 # Increased for better convergence
BATCH_SIZE = 64
GAMMA = 0.90 
EPS_START = 1.0
EPS_END = 0.02
EPS_DECAY = 0.997

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("GATEKEEPER_V2")

# --- RL ENVIRONMENT ---
class GatekeeperEnv:
    def __init__(self, trajectories):
        self.dataset = []
        
        # Pre-calculate stats for normalization
        vols = []
        atrs = []
        
        for t in trajectories:
            if 'history' not in t or not t['history']: continue
            
            # 1. Parse Time Features
            try:
                dt = datetime.strptime(t['entry_time'], "%Y-%m-%d %H:%M:%S")
                hour_norm = dt.hour / 23.0
                day_norm = dt.weekday() / 6.0
            except:
                hour_norm = 0.5
                day_norm = 0.5
            
            # 2. Extract Technical Features (at Entry)
            initial_step = t['history'][0]
            
            ema_slope = initial_step.get('ema_9_slope', 0)
            vol = initial_step.get('vol', 0)
            atr = initial_step.get('atr_norm', 0)
            
            vols.append(vol)
            atrs.append(atr)
            
            state_raw = [ema_slope, vol, atr, hour_norm, day_norm]
            outcome = t.get('final_outcome_r', 0)
            
            self.dataset.append({
                'state_raw': state_raw,
                'outcome': outcome
            })
            
        # 3. Robust Scaling (IQR) to handle outliers
        self.vol_median = np.median(vols)
        self.vol_iqr = np.percentile(vols, 75) - np.percentile(vols, 25)
        self.atr_median = np.median(atrs)
        self.atr_iqr = np.percentile(atrs, 75) - np.percentile(atrs, 25)
        
        # Normalize dataset
        for item in self.dataset:
            sr = item['state_raw']
            # Scale Vol and ATR
            vol_scaled = (sr[1] - self.vol_median) / (self.vol_iqr + 1e-6)
            atr_scaled = (sr[2] - self.atr_median) / (self.atr_iqr + 1e-6)
            # Clip to [-3, 3] to prevent extreme outliers from destabilizing NN
            vol_scaled = np.clip(vol_scaled, -3, 3)
            atr_scaled = np.clip(atr_scaled, -3, 3)
            
            # Final State: [EMA_Slope, Vol_Z, ATR_Z, Hour, Day]
            item['state'] = np.array([sr[0], vol_scaled, atr_scaled, sr[3], sr[4]], dtype=np.float32)
            
        logger.info(f"Loaded {len(self.dataset)} trades. Vol Median={self.vol_median:.4f}")
        self.reset()
        
    def reset(self):
        self.current_scenario = random.choice(self.dataset)
        return self.current_scenario['state']

    def step(self, action):
        """
        Action 0: REJECT -> Reward 0
        Action 1: ACCEPT -> Reward = Actual Outcome R
        """
        if action == 1:
            reward = self.current_scenario['outcome']
        else:
            reward = 0
        return self.current_scenario['state'], reward, True, {}

# --- Q-NETWORK (Deeper for v2) ---
class GatekeeperQNet(nn.Module):
    def __init__(self, state_dim=5, action_dim=2):
        super(GatekeeperQNet, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.1), # Prevent Overfitting
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, action_dim)
        )
    def forward(self, x):
        return self.net(x)

# --- TRAINING ENGINE ---
def train():
    logger.info(f"Loading trajectories v2 from {DATA_PATH}...")
    if not os.path.exists(DATA_PATH):
        logger.error(f"❌ DATA PATH NOT FOUND: {DATA_PATH}")
        return

    with open(DATA_PATH, 'r') as f:
        trajs = json.load(f)
    
    env = GatekeeperEnv(trajs)
    q_net = GatekeeperQNet()
    optimizer = optim.Adam(q_net.parameters(), lr=0.0005)
    loss_fn = nn.SmoothL1Loss() # Huber Loss is better for noisy rewards
    memory = deque(maxlen=20000)
    
    eps = EPS_START
    
    accepted_outcomes = []
    
    for ep in range(EPISODES):
        state = env.reset()
        
        if random.random() < eps:
            action = random.randint(0, 1)
        else:
            q_net.eval()
            with torch.no_grad():
                state_t = torch.FloatTensor(state).unsqueeze(0)
                action = q_net(state_t).argmax().item()
            q_net.train()
        
        _, reward, _, _ = env.step(action)
        memory.append((state, action, reward))
        
        if action == 1: accepted_outcomes.append(reward)
            
        if len(memory) > BATCH_SIZE:
            batch = random.sample(memory, BATCH_SIZE)
            s_batch, a_batch, r_batch = zip(*batch)
            
            s_batch = torch.FloatTensor(np.array(s_batch))
            a_batch = torch.LongTensor(a_batch).unsqueeze(1)
            r_batch = torch.FloatTensor(r_batch).unsqueeze(1)
            
            current_q = q_net(s_batch).gather(1, a_batch)
            loss = loss_fn(current_q, r_batch)
            
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
        eps = max(EPS_END, eps * EPS_DECAY)
        
        if ep % 500 == 0:
            avg_r = np.mean(accepted_outcomes[-100:]) if accepted_outcomes else 0
            logger.info(f"EP {ep} | Eps: {eps:.2f} | Last 100 Acc R: {avg_r:.2f}")

    # --- EVALUATION ---
    logger.info("Evaluating V2 Policy...")
    q_net.eval()
    
    eval_accepted = []
    eval_rejected = []
    
    # Deterministic Evaluation on Full Dataset
    for scenario in env.dataset:
        state = scenario['state']
        outcome = scenario['outcome']
        
        with torch.no_grad():
            state_t = torch.FloatTensor(state).unsqueeze(0)
            action = q_net(state_t).argmax().item()
            
        if action == 1:
            eval_accepted.append(outcome)
        else:
            eval_rejected.append(outcome)
    
    all_outcomes = [x['outcome'] for x in env.dataset]
    
    print("\n" + "="*60)
    print("🧠 RL GATEKEEPER V2 REPORT (Feature Engineered)")
    print("="*60)
    
    base_r = np.mean(all_outcomes)
    base_wr = np.mean(np.array(all_outcomes) > 0) * 100
    
    gate_r = np.mean(eval_accepted) if eval_accepted else 0
    gate_wr = np.mean(np.array(eval_accepted) > 0) * 100 if eval_accepted else 0
    
    print(f"{'METRIC':<15} | {'BASELINE':<15} | {'GATEKEEPER V2':<15} | {'DELTA':<10}")
    print("-" * 65)
    print(f"{'Trades':<15} | {len(all_outcomes):<15} | {len(eval_accepted):<15} | -{len(eval_rejected)}")
    print(f"{'Rejection %':<15} | {'0%':<15} | {(len(eval_rejected)/len(all_outcomes))*100:.1f}%{'':<15} |")
    print("-" * 65)
    print(f"{'Avg R':<15} | {base_r:<15.3f} | {gate_r:<15.3f} | {gate_r-base_r:+.3f}")
    print(f"{'Win Rate':<15} | {base_wr:<15.1f}% | {gate_wr:<15.1f}% | {gate_wr-base_wr:+.1f}%")
    print(f"{'Total R':<15} | {np.sum(all_outcomes):<15.1f} | {np.sum(eval_accepted):<15.1f} | {np.sum(eval_accepted)-np.sum(all_outcomes):+.1f}")
    print("="*60 + "\n")
    
    # Save Model
    os.makedirs(os.path.dirname(MODEL_SAVE_PATH), exist_ok=True)
    torch.save(q_net.state_dict(), MODEL_SAVE_PATH)
    logger.info(f"Model saved to {MODEL_SAVE_PATH}")
    
    # Save Scaler Params
    scaler_params = {
        "vol_median": env.vol_median,
        "vol_iqr": env.vol_iqr,
        "atr_median": env.atr_median,
        "atr_iqr": env.atr_iqr
    }
    with open(SCALER_SAVE_PATH, "w") as f:
        json.dump(scaler_params, f, indent=4)
    logger.info(f"Scaler params saved to {SCALER_SAVE_PATH}")

if __name__ == "__main__":
    train()
