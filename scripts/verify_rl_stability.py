#!/usr/bin/env python3
"""
RL Stability Verification Script
Trains the agent 5 times with different random seeds.
Evaluates each model on the blind test set to measure Alpha variance.
"""
import os
import json
import numpy as np
import torch
import torch.nn as nn
import random
import torch.optim as optim
from collections import deque

# --- SETTINGS ---
DATA_PATH = "data/research/rl_trajectories_v1.json"
MODEL_TMP_PATH = "models/tmp_rl_stability.pth"

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

class TradeEnv:
    def __init__(self, trajectories):
        self.trajectories = trajectories
        self.current_traj = None
        self.current_step = 0
        self.sl_r = 0.0
        self.is_closed = False
        
    def reset(self):
        self.current_traj = random.choice(self.trajectories)
        self.current_step = 0
        self.sl_r = 0.0
        self.is_closed = False
        return self._get_state()
        
    def _get_state(self):
        step_data = self.current_traj['history'][self.current_step]
        return np.array([
            step_data['current_r'],
            step_data['max_r'],
            step_data['ema_9_slope'],
            step_data['vol'],
            step_data['atr_norm'],
            self.sl_r
        ], dtype=np.float32)
        
    def step(self, action):
        reward = 0
        done = False
        if action == 2:
            self.is_closed = True
            reward = self.current_traj['history'][self.current_step]['current_r']
            done = True
        elif action == 1:
            self.sl_r += 0.5
        if not done:
            self.current_step += 1
            if self.current_step >= len(self.current_traj['history']):
                reward = self.current_traj['history'][-1]['current_r']
                done = True
            else:
                step_data = self.current_traj['history'][self.current_step]
                if step_data['current_r'] <= self.sl_r:
                    reward = self.sl_r
                    done = True
        next_state = self._get_state() if not done else np.zeros(6, dtype=np.float32)
        return next_state, reward, done

def train_and_eval(seed, train_trajs, test_trajs):
    # Setup seeds
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    
    state_dim = 6
    action_dim = 3
    q_net = QNetwork(state_dim, action_dim)
    target_net = QNetwork(state_dim, action_dim)
    target_net.load_state_dict(q_net.state_dict())
    optimizer = optim.Adam(q_net.parameters(), lr=0.001)
    memory = deque(maxlen=10000)
    
    env = TradeEnv(train_trajs)
    batch_size = 64
    gamma = 0.99
    epsilon = 1.0
    epsilon_decay = 0.99
    
    # Accelerated training for stability test
    for _ in range(500):
        state = env.reset()
        done = False
        while not done:
            if random.random() < epsilon: action = random.randint(0, 2)
            else:
                with torch.no_grad(): action = q_net(torch.FloatTensor(state).unsqueeze(0)).argmax().item()
            next_state, reward, done = env.step(action)
            memory.append((state, action, reward, next_state, done))
            state = next_state
            if len(memory) > batch_size:
                batch = random.sample(memory, batch_size)
                s, a, r, ns, d = zip(*batch)
                s_t = torch.FloatTensor(np.array(s))
                a_t = torch.LongTensor(a).unsqueeze(1)
                r_t = torch.FloatTensor(r).unsqueeze(1)
                ns_t = torch.FloatTensor(np.array(ns))
                d_t = torch.FloatTensor(d).unsqueeze(1)
                curr_q = q_net(s_t).gather(1, a_t)
                next_q = target_net(ns_t).max(1)[0].unsqueeze(1)
                target_q = r_t + (1 - d_t) * gamma * next_q
                loss = nn.MSELoss()(curr_q, target_q)
                optimizer.zero_grad(); loss.backward(); optimizer.step()
        epsilon = max(0.1, epsilon * epsilon_decay)
        
    # Evaluate
    q_net.eval()
    total_r = 0.0
    for traj in test_trajs:
        sl_r = 0.0
        for entry in traj['history']:
            state = np.array([entry['current_r'], entry['max_r'], entry['ema_9_slope'], entry['vol'], entry['atr_norm'], sl_r], dtype=np.float32)
            with torch.no_grad(): action = q_net(torch.FloatTensor(state).unsqueeze(0)).argmax().item()
            if action == 2:
                total_r += entry['current_r']
                break
            elif action == 1: sl_r += 0.5
            if entry['current_r'] <= sl_r:
                total_r += sl_r
                break
        else: total_r += traj['history'][-1]['current_r']
    return total_r

def run_stability():
    with open(DATA_PATH, 'r') as f:
        trajs = json.load(f)
    split = int(len(trajs) * 0.7)
    train_t, test_t = trajs[:split], trajs[split:]
    
    seeds = [42, 1337, 7, 123, 99]
    results = []
    print(f"🔄 Running Stability Test (5 Seeds)...")
    for s in seeds:
        r = train_and_eval(s, train_t, test_t)
        results.append(r)
        print(f"Seed {s} | Total R: {r:.2f}")
    
    print("\n" + "="*40)
    print("🛡️  STABILITY REPORT")
    print("="*40)
    print(f"Mean R: {np.mean(results):.2f}")
    print(f"Std Dev: {np.std(results):.2f}")
    print(f"Min R: {np.min(results):.2f}")
    print(f"Max R: {np.max(results):.2f}")
    print("="*40)

if __name__ == "__main__":
    run_stability()
