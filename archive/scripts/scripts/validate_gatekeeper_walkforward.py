#!/usr/bin/env python3
"""
Phase 18: Strict Walk-Forward Validation
Train: 2025 Data | Test: 2026 Data
Analyzes Generalization, Drawdown Impact, and Trade Frequency.
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
DATA_PATH = "data/research/rl_trajectories_v1.json"
SPLIT_DATE = "2026-01-01"
EPISODES = 2000
BATCH_SIZE = 64
GAMMA = 0.90
EPS_START = 1.0
EPS_END = 0.05
EPS_DECAY = 0.995

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("WALK_FORWARD")

class GatekeeperQNet(nn.Module):
    def __init__(self, state_dim=5, action_dim=2):
        super(GatekeeperQNet, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.2), # Higher dropout for generalization
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, action_dim)
        )
    def forward(self, x):
        return self.net(x)

def load_and_split_data():
    with open(DATA_PATH, 'r') as f:
        raw_data = json.load(f)
    
    # Process and Normalize
    processed_data = []
    
    # Pre-pass to get scaling params (computed on TRAIN ONLY to avoid leak)
    train_vols = []
    train_atrs = []
    
    # First pass: parse dates and identify split
    temp_data = []
    for t in raw_data:
        if 'history' not in t or not t['history']: continue
        try:
            dt = datetime.strptime(t['entry_time'], "%Y-%m-%d %H:%M:%S")
            t['dt'] = dt
            temp_data.append(t)
        except: continue
        
    temp_data.sort(key=lambda x: x['dt'])
    split_dt = datetime.strptime(SPLIT_DATE, "%Y-%m-%d")
    
    train_set_raw = [t for t in temp_data if t['dt'] < split_dt]
    test_set_raw = [t for t in temp_data if t['dt'] >= split_dt]
    
    # Calc stats on TRAIN
    for t in train_set_raw:
        h0 = t['history'][0]
        train_vols.append(h0.get('vol', 0))
        train_atrs.append(h0.get('atr_norm', 0))
        
    vol_median = np.median(train_vols)
    vol_iqr = np.percentile(train_vols, 75) - np.percentile(train_vols, 25)
    atr_median = np.median(train_atrs)
    atr_iqr = np.percentile(train_atrs, 75) - np.percentile(train_atrs, 25)
    
    def process_subset(subset):
        dataset = []
        for t in subset:
            dt = t['dt']
            h0 = t['history'][0]
            
            # Features
            hour_norm = dt.hour / 23.0
            day_norm = dt.weekday() / 6.0
            ema_slope = h0.get('ema_9_slope', 0)
            
            # Scale
            vol = np.clip((h0.get('vol', 0) - vol_median) / (vol_iqr + 1e-6), -3, 3)
            atr = np.clip((h0.get('atr_norm', 0) - atr_median) / (atr_iqr + 1e-6), -3, 3)
            
            state = np.array([ema_slope, vol, atr, hour_norm, day_norm], dtype=np.float32)
            outcome = t.get('final_outcome_r', 0)
            
            dataset.append({
                'state': state,
                'outcome': outcome,
                'dt': dt
            })
        return dataset
        
    return process_subset(train_set_raw), process_subset(test_set_raw), {
        'vol_median': vol_median, 'vol_iqr': vol_iqr, 
        'atr_median': atr_median, 'atr_iqr': atr_iqr
    }

def calculate_metrics(dataset, accepted_indices):
    if not dataset: return {}
    
    # Baseline
    all_outcomes = [d['outcome'] for d in dataset]
    base_r = np.mean(all_outcomes)
    base_wr = np.mean(np.array(all_outcomes) > 0)
    
    # Gatekeeper
    accepted_outcomes = [dataset[i]['outcome'] for i in accepted_indices]
    gate_r = np.mean(accepted_outcomes) if accepted_outcomes else 0
    gate_wr = np.mean(np.array(accepted_outcomes) > 0) if accepted_outcomes else 0
    
    # Drawdown (Simulated on 1% risk)
    equity = 10000
    peak = 10000
    max_dd = 0
    
    # Sort accepted by time for DD calc (already sorted in load)
    # But accepted_indices matches dataset order
    for i in accepted_indices:
        r = dataset[i]['outcome']
        pnl = equity * 0.01 * r
        equity += pnl
        if equity > peak: peak = equity
        dd = (peak - equity) / peak
        if dd > max_dd: max_dd = dd
        
    # Baseline DD
    base_equity = 10000
    base_peak = 10000
    base_max_dd = 0
    for d in dataset:
        r = d['outcome']
        pnl = base_equity * 0.01 * r
        base_equity += pnl
        if base_equity > base_peak: base_peak = base_equity
        dd = (base_peak - base_equity) / base_peak
        if dd > base_max_dd: base_max_dd = dd
        
    # Silence (Max hours between trades)
    max_silence_hours = 0
    last_time = None
    
    for i in accepted_indices:
        curr_time = dataset[i]['dt']
        if last_time:
            diff = (curr_time - last_time).total_seconds() / 3600.0
            if diff > max_silence_hours: max_silence_hours = diff
        last_time = curr_time
        
    return {
        'count': len(dataset),
        'accepted': len(accepted_indices),
        'base_wr': base_wr * 100,
        'gate_wr': gate_wr * 100,
        'base_r': base_r,
        'gate_r': gate_r,
        'base_dd': base_max_dd * 100,
        'gate_dd': max_dd * 100,
        'max_silence': max_silence_hours
    }

def train_and_validate():
    logger.info("Loading and Splitting Data...")
    train_data, test_data, scaler_params = load_and_split_data()
    logger.info(f"Train Set (2025): {len(train_data)} trades")
    logger.info(f"Test Set (2026): {len(test_data)} trades")
    
    # --- TRAIN ---
    q_net = GatekeeperQNet()
    optimizer = optim.Adam(q_net.parameters(), lr=0.0005)
    loss_fn = nn.SmoothL1Loss()
    memory = deque(maxlen=10000)
    
    eps = EPS_START
    
    logger.info("Training on 2025 Data...")
    for ep in range(EPISODES):
        scenario = random.choice(train_data)
        state = scenario['state']
        
        if random.random() < eps:
            action = random.randint(0, 1)
        else:
            with torch.no_grad():
                action = q_net(torch.FloatTensor(state).unsqueeze(0)).argmax().item()
        
        outcome = scenario['outcome'] if action == 1 else 0
        
        memory.append((state, action, outcome))
        
        if len(memory) > BATCH_SIZE:
            batch = random.sample(memory, BATCH_SIZE)
            s, a, r = zip(*batch)
            current_q = q_net(torch.FloatTensor(np.array(s))).gather(1, torch.LongTensor(a).unsqueeze(1))
            loss = loss_fn(current_q, torch.FloatTensor(r).unsqueeze(1))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
        eps = max(EPS_END, eps * EPS_DECAY)
    
    # --- EVALUATE ON FULL DATASET (For DD Comparison) ---
    logger.info("Evaluating on FULL Dataset (DD Impact)...")
    q_net.eval()
    
    # Reload raw and process all
    with open(DATA_PATH, 'r') as f:
        raw_data = json.load(f)
    
    full_processed = []
    for t in raw_data:
        if 'history' not in t or not t['history']: continue
        try:
            dt = datetime.strptime(t['entry_time'], "%Y-%m-%d %H:%M:%S")
        except: continue
        
        h0 = t['history'][0]
        # Features
        hour_norm = dt.hour / 23.0
        day_norm = dt.weekday() / 6.0
        ema_slope = h0.get('ema_9_slope', 0)
        
        # Scaled using TRAINING params (consistency)
        vol = np.clip((h0.get('vol', 0) - scaler_params['vol_median']) / (scaler_params['vol_iqr'] + 1e-6), -3, 3)
        atr = np.clip((h0.get('atr_norm', 0) - scaler_params['atr_median']) / (scaler_params['atr_iqr'] + 1e-6), -3, 3)
        
        state = np.array([ema_slope, vol, atr, hour_norm, day_norm], dtype=np.float32)
        full_processed.append({'state': state, 'outcome': t.get('final_outcome_r', 0), 'dt': dt})

    full_processed.sort(key=lambda x: x['dt'])
    
    accepted_indices = []
    for i, scenario in enumerate(full_processed):
        with torch.no_grad():
            action = q_net(torch.FloatTensor(scenario['state']).unsqueeze(0)).argmax().item()
        if action == 1:
            accepted_indices.append(i)
            
    metrics = calculate_metrics(full_processed, accepted_indices)
    
    print("\n" + "="*60)
    print("📉 FULL DATASET IMPACT ANALYSIS (All History)")
    print("="*60)
    print(f"{'Metric':<20} | {'Baseline (No Filter)':<20} | {'Gatekeeper (AI)':<20} | {'Delta':<10}")
    print("-" * 75)
    print(f"{'Win Rate':<20} | {metrics['base_wr']:<20.2f}% | {metrics['gate_wr']:<20.2f}% | {metrics['gate_wr']-metrics['base_wr']:+.2f}%")
    print(f"{'Avg R (Profit)':<20} | {metrics['base_r']:<20.3f}R | {metrics['gate_r']:<20.3f}R | {metrics['gate_r']-metrics['base_r']:+.3f}R")
    print(f"{'Max Drawdown':<20} | {metrics['base_dd']:<20.2f}% | {metrics['gate_dd']:<20.2f}% | {metrics['gate_dd']-metrics['base_dd']:+.2f}%")
    print("-" * 75)
    print(f"{'Trades Accepted':<20} | {metrics['count']:<20} | {metrics['accepted']:<20} | {(metrics['accepted']/metrics['count'])*100:.1f}% kept")
    print("="*60 + "\n")

if __name__ == "__main__":
    train_and_validate()
