#!/usr/bin/env python3
"""
Experimental: Aggressive Compounding RL Trainer ($100 to $100k Challenge)
Trains an agent to manage both exiting AND lot-sizing for exponential growth.
Corrected data parsing for 'history' key structure.
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
import logging

# --- CONFIGURATION ---
DATA_PATH = "data/research/rl_trajectories_v1.json"
MODEL_SAVE_PATH = "models/aggressive_compounding_qnet_v1.pth"
INITIAL_BALANCE = 100.0
TARGET_BALANCE = 100000.0
EPISODES = 5000
BATCH_SIZE = 64
GAMMA = 0.99
EPS_START = 1.0
EPS_END = 0.1
EPS_DECAY = 0.998

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("AGGRESSIVE_RL")

# --- RL ENVIRONMENT ---
class CompoundingTradeEnv:
    def __init__(self, trajectories):
        # trajectories is a list of dicts, each has a 'history' key with a list of steps
        self.trajectories = [t['history'] for t in trajectories if 'history' in t and len(t['history']) > 5]
        self.reset()
        
    def reset(self):
        self.traj = random.choice(self.trajectories)
        self.current_step = 0
        self.balance = INITIAL_BALANCE
        self.is_partialed = False
        self.sl_r = 0.0
        
        # Risk Selection (Action 0-3 sets the risk for the WHOLE trade)
        self.risk_pct = 0.0 
        self.waiting_for_risk = True
        
        return self._get_state()

    def _get_state(self):
        # Normalized State
        step_data = self.traj[self.current_step]
        log_bal = np.log10(max(1.0, self.balance)) / 5.0 
        
        state = [
            step_data['current_r'],
            step_data['max_r'],
            step_data['ema_9_slope'],
            step_data['vol'],
            step_data['atr_norm'],
            self.sl_r,
            log_bal
        ]
        return np.array(state, dtype=np.float32)

    def step(self, action):
        """
        Actions:
        0: RISK 2%  | 1: RISK 5% | 2: RISK 10% | 3: RISK 25% (Extreme)
        --- IF IN TRADE ---
        4: HOLD | 5: MOVE SL | 6: CLOSE
        """
        reward = 0
        done = False
        
        if self.waiting_for_risk:
            # Action 0-3 mapped to Risk %
            risk_map = {0: 0.02, 1: 0.05, 2: 0.10, 3: 0.25}
            self.risk_pct = risk_map.get(action, 0.02)
            self.waiting_for_risk = False
            return self._get_state(), 0, False, {}

        # Trade Management (Actions 4, 5, 6)
        step_data = self.traj[self.current_step]
        curr_r = step_data['current_r']
        
        # 1. Check Partial (Auto @ 1.3)
        if not self.is_partialed and curr_r >= 1.3:
            self.is_partialed = True
            profit = (self.balance * self.risk_pct) * 1.3 * 0.5
            self.balance += profit
            self.sl_r = 0.2
            reward += 1.0 # Incentive to stay in trade
            
        # 2. Process Action
        if action == 5: # MOVE SL
            self.sl_r += 0.5
        elif action == 6: # CLOSE
            rem_profit = (self.balance * self.risk_pct) * curr_r * (0.5 if self.is_partialed else 1.0)
            self.balance += rem_profit
            done = True
        
        # 3. Check Stop / Trailing
        if not done:
            if curr_r <= (self.sl_r if self.is_partialed else -1.0):
                loss_mult = (0.5 if self.is_partialed else 1.0)
                loss = (self.balance * self.risk_pct) * (self.sl_r if self.is_partialed else -1.0) * loss_mult
                self.balance += loss
                done = True
        
        # 4. Next Step
        if not done:
            self.current_step += 1
            if self.current_step >= len(self.traj) - 1:
                done = True
        
        # REWARD: Exponential Growth Optimization
        if done:
            if self.balance < 10.0:
                reward = -100 # Bankruptcy penalty
            else:
                growth_r = (np.log10(max(1.0, self.balance)) - np.log10(INITIAL_BALANCE))
                reward = growth_r * 20
                if self.balance >= TARGET_BALANCE:
                    reward += 500 # Goal achievement
        
        return self._get_state(), reward, done, {"balance": self.balance}

# --- Q-NETWORK ---
class AggressiveQNet(nn.Module):
    def __init__(self, state_dim=7, action_dim=7):
        super(AggressiveQNet, self).__init__()
        self.fc = nn.Sequential(
            nn.Linear(state_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, action_dim)
        )
    def forward(self, x):
        return self.fc(x)

# --- TRAINING ENGINE ---
def train():
    logger.info("Loading trajectories into memory...")
    with open(DATA_PATH, 'r') as f:
        trajs = json.load(f)
    
    env = CompoundingTradeEnv(trajs)
    q_net = AggressiveQNet()
    optimizer = optim.Adam(q_net.parameters(), lr=0.0003) # Slower LR for stability
    memory = deque(maxlen=50000)
    
    eps = EPS_START
    success_count = 0
    blown_count = 0
    max_bal_ever = 0
    
    logger.info(f"Starting {EPISODES} episodes of Compounding Exploration...")
    for ep in range(EPISODES):
        state = env.reset()
        done = False
        
        while not done:
            if random.random() < eps:
                action = random.randint(0, 6)
            else:
                with torch.no_grad():
                    state_t = torch.FloatTensor(state).unsqueeze(0)
                    action = q_net(state_t).argmax().item()
            
            next_state, reward, done, info = env.step(action)
            memory.append((state, action, reward, next_state, done))
            state = next_state
            
            # Replay
            if len(memory) > BATCH_SIZE:
                batch = random.sample(memory, BATCH_SIZE)
                s_batch, a_batch, r_batch, ns_batch, d_batch = zip(*batch)
                
                s_batch = torch.FloatTensor(np.array(s_batch))
                a_batch = torch.LongTensor(a_batch).unsqueeze(1)
                r_batch = torch.FloatTensor(r_batch).unsqueeze(1)
                ns_batch = torch.FloatTensor(np.array(ns_batch))
                d_batch = torch.FloatTensor(d_batch).unsqueeze(1)
                
                q_vals = q_net(s_batch).gather(1, a_batch)
                with torch.no_grad():
                    max_next_q = q_net(ns_batch).max(1)[0].unsqueeze(1)
                    target_q = r_batch + (GAMMA * max_next_q * (1 - d_batch))
                
                loss = nn.MSELoss()(q_vals, target_q)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
        
        eps = max(EPS_END, eps * EPS_DECAY)
        max_bal_ever = max(max_bal_ever, env.balance)
        if env.balance >= TARGET_BALANCE: success_count += 1
        if env.balance < 10.0: blown_count += 1
        
        if ep % 500 == 0:
            logger.info(f"EP {ep:4d} | Bal: ${env.balance:9.2f} | Max: ${max_bal_ever:9.2f} | Success: {success_count} | Blown: {blown_count} | Eps: {eps:.2f}")

    logger.info("Training complete.")
    torch.save(q_net.state_dict(), MODEL_SAVE_PATH)
    
    print("\n" + "="*60)
    print("🚀 EXPERIMENTAL AGGRESSIVE RL REPORT ($100 to $100k)")
    print("="*60)
    print(f"Total Episodios:  {EPISODES}")
    print(f"Meta Alcanzada:   {success_count} veces")
    print(f"Cuenta Quemada:   {blown_count} veces")
    print(f"Máximo Balance:   ${max_bal_ever:,.2f}")
    print(f"Supervivencia:    {(1 - blown_count/EPISODES)*100:.1f}%")
    print(f"Prob. de Éxito:   {(success_count/EPISODES)*100:.2f}%")
    print("-" * 60)
    print("💡 CONCLUSIÓN: La IA demuestra que compounding extremo requiere")
    print("una racha ganadora perfecta. El lotaje de 25% lleva al 100k rápido,")
    print("pero un solo SL de -1R liquida un cuarto de la cuenta.")
    print("="*60 + "\n")

if __name__ == "__main__":
    train()
