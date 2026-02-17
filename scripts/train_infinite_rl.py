#!/usr/bin/env python3
"""
RL Infinite Trailing Trainer
Trains a Q-Learning agent (using a small NN) to manage the Infinite Runner.
Environment simulates the trade state bar-by-bar.
"""
import os
import json
import numpy as np
import random
import torch
import torch.nn as nn
import torch.optim as optim
from collections import deque

# --- SETTINGS ---
DATA_PATH = "data/research/rl_trajectories_v1.json"
MODEL_PATH = "models/infinite_rl_qnet_v1.pth"

# Simple Q-Network (8 units for the user spec)
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
        self.sl_r = 0.0 # Initial SL at Entry (BE)
        self.is_closed = False
        return self._get_state()
        
    def _get_state(self):
        step_data = self.current_traj['history'][self.current_step]
        # State: [current_r, max_r, ema_slope, vol, atr_norm, current_sl_r]
        return np.array([
            step_data['current_r'],
            step_data['max_r'],
            step_data['ema_9_slope'],
            step_data['vol'],
            step_data['atr_norm'],
            self.sl_r
        ], dtype=np.float32)
        
    def step(self, action):
        """
        Actions: 0: HOLD, 1: MOVE STOP (+0.5R), 2: CLOSE
        """
        reward = 0
        done = False
        
        if action == 2: # CLOSE
            self.is_closed = True
            reward = self.current_traj['history'][self.current_step]['current_r']
            done = True
        elif action == 1: # MOVE STOP
            self.sl_r += 0.5
            
        if not done:
            self.current_step += 1
            if self.current_step >= len(self.current_traj['history']):
                # Natural end of history
                reward = self.current_traj['history'][-1]['current_r']
                done = True
            else:
                # Check if SL hit
                step_data = self.current_traj['history'][self.current_step]
                if step_data['current_r'] <= self.sl_r:
                    # SL Hit!
                    reward = self.sl_r
                    done = True
        
        next_state = self._get_state() if not done else np.zeros(6, dtype=np.float32)
        return next_state, reward, done

def train_rl():
    if not os.path.exists(DATA_PATH):
        print("❌ Dataset not found")
        return
        
    with open(DATA_PATH, 'r') as f:
        trajectories = json.load(f)
        
    # Institutional Split: Train on first 70%, Test on last 30%
    split_idx = int(len(trajectories) * 0.7)
    train_trajectories = trajectories[:split_idx]
    
    env = TradeEnv(train_trajectories)
    state_dim = 6
    action_dim = 3
    
    q_net = QNetwork(state_dim, action_dim)
    target_net = QNetwork(state_dim, action_dim)
    target_net.load_state_dict(q_net.state_dict())
    
    optimizer = optim.Adam(q_net.parameters(), lr=0.001)
    memory = deque(maxlen=10000)
    
    batch_size = 64
    gamma = 0.99
    epsilon = 1.0
    epsilon_min = 0.1
    epsilon_decay = 0.995
    
    print(f"🤖 Training RL Agent on {len(trajectories)} trajectories...")
    
    for episode in range(1000):
        state = env.reset()
        total_reward = 0
        done = False
        
        while not done:
            # Epsilon-greedy
            if random.random() < epsilon:
                action = random.randint(0, action_dim - 1)
            else:
                with torch.no_grad():
                    state_t = torch.FloatTensor(state).unsqueeze(0)
                    action = q_net(state_t).argmax().item()
            
            next_state, reward, done = env.step(action)
            memory.append((state, action, reward, next_state, done))
            state = next_state
            total_reward += reward
            
            # Replay
            if len(memory) > batch_size:
                batch = random.sample(memory, batch_size)
                states, actions, rewards, next_states, dones = zip(*batch)
                
                states_t = torch.FloatTensor(np.array(states))
                actions_t = torch.LongTensor(actions).unsqueeze(1)
                rewards_t = torch.FloatTensor(rewards).unsqueeze(1)
                next_states_t = torch.FloatTensor(np.array(next_states))
                dones_t = torch.FloatTensor(dones).unsqueeze(1)
                
                current_q = q_net(states_t).gather(1, actions_t)
                next_q = target_net(next_states_t).max(1)[0].unsqueeze(1)
                target_q = rewards_t + (1 - dones_t) * gamma * next_q
                
                loss = nn.MSELoss()(current_q, target_q)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
        
        epsilon = max(epsilon_min, epsilon * epsilon_decay)
        
        if episode % 100 == 0:
            target_net.load_state_dict(q_net.state_dict())
            print(f"Episode {episode} | Epsilon: {epsilon:.2f} | Avg Reward (last 100): {total_reward:.2f}")

    os.makedirs("models", exist_ok=True)
    torch.save(q_net.state_dict(), MODEL_PATH)
    print(f"💾 RL Model saved to {MODEL_PATH}")

if __name__ == "__main__":
    train_rl()
