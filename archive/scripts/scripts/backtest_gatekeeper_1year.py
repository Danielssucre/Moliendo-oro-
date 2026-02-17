#!/usr/bin/env python3
"""
Harmonized Backtest: Gatekeeper v2.0 + Runner v1.2
Simulates 1 Year of trading with the AI Filter.
Metrics: Win Rate, Sharpe, PF, DD.
"""
import os
import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from datetime import datetime
import matplotlib.pyplot as plt

# --- CONFIGURATION ---
DATA_PATH = "data/research/rl_trajectories_v1.json"
MODEL_PATH = "models/gatekeeper_qnet_v2.pth"
INITIAL_CAPITAL = 10000.0
RISK_PER_TRADE = 0.01  # 1% Risk (Standard Institutional)

# --- GATEKEEPER MODEL DEFINITION (Must match training script) ---
class GatekeeperQNet(nn.Module):
    def __init__(self, state_dim=5, action_dim=2):
        super(GatekeeperQNet, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, action_dim)
        )
    def forward(self, x):
        return self.net(x)

def load_data():
    with open(DATA_PATH, 'r') as f:
        return json.load(f)

def run_backtest():
    print("🚀 Starting Harmonized Backtest (Gatekeeper + Runner)...")
    
    # 1. Load Data & Model
    trajs = load_data()
    model = GatekeeperQNet()
    try:
        model.load_state_dict(torch.load(MODEL_PATH))
        model.eval()
        print(f"✅ Loaded Gatekeeper Model: {MODEL_PATH}")
    except FileNotFoundError:
        print("❌ Model not found! Train it first.")
        return

    # 2. Prepare Feature Scaling (From Training Script Logic)
    # We need to re-calculate median/IQR to ensure consistent scaling
    vols = []
    atrs = []
    for t in trajs:
        if 'history' in t and t['history']:
            vols.append(t['history'][0].get('vol', 0))
            atrs.append(t['history'][0].get('atr_norm', 0))
            
    vol_median = np.median(vols)
    vol_iqr = np.percentile(vols, 75) - np.percentile(vols, 25)
    atr_median = np.median(atrs)
    atr_iqr = np.percentile(atrs, 75) - np.percentile(atrs, 25)

    # 3. Simulation Loop
    balance = INITIAL_CAPITAL
    equity_curve = [balance]
    trades = []
    
    # Sort by time to ensure correct drawdown calculation
    # (Assuming trajectories are somewhat ordered or we sort them)
    # The dataset might be mixed symbols, so sorting is crucial for correct Timeline.
    # Parse dates first
    for t in trajs:
        try:
            t['dt'] = datetime.strptime(t['entry_time'], "%Y-%m-%d %H:%M:%S")
        except:
            t['dt'] = datetime.min
            
    trajs.sort(key=lambda x: x['dt'])
    
    print(f"📅 Period: {trajs[0]['entry_time']} to {trajs[-1]['entry_time']}")
    
    accepted_count = 0
    rejected_count = 0
    
    for t in trajs:
        if 'history' not in t or not t['history']: continue
        
        # --- A. Gatekeeper Decision ---
        # 1. Extract Features
        try:
            dt = t['dt']
            hour_norm = dt.hour / 23.0
            day_norm = dt.weekday() / 6.0
        except:
            hour_norm = 0.5
            day_norm = 0.5
            
        initial_step = t['history'][0]
        ema_slope = initial_step.get('ema_9_slope', 0)
        vol = initial_step.get('vol', 0)
        atr = initial_step.get('atr_norm', 0)
        
        # 2. Scale
        vol_scaled = np.clip((vol - vol_median) / (vol_iqr + 1e-6), -3, 3)
        atr_scaled = np.clip((atr - atr_median) / (atr_iqr + 1e-6), -3, 3)
        
        state = np.array([ema_slope, vol_scaled, atr_scaled, hour_norm, day_norm], dtype=np.float32)
        
        # 3. Predict
        with torch.no_grad():
            state_t = torch.FloatTensor(state).unsqueeze(0)
            action = model(state_t).argmax().item()
            
        if action == 0: # REJECT
            rejected_count += 1
            continue
            
        accepted_count += 1
        
        # --- B. Trade Execution (Runner Logic) ---
        # We use the 'final_outcome_r' which represents the Runner's realized R-Multiple
        r_multiple = t.get('final_outcome_r', 0)
        
        # Calculate PnL
        # Risk Amount = Balance * Risk%
        risk_amount = balance * RISK_PER_TRADE
        pnl = risk_amount * r_multiple
        
        balance += pnl
        equity_curve.append(balance)
        
        trades.append({
            'time': t['entry_time'],
            'symbol': t.get('symbol', 'UNKNOWN'),
            'type': 'BUY' if 'BUY' in str(t) else 'SELL', # Approximate
            'outcome_r': r_multiple,
            'pnl': pnl,
            'balance': balance
        })

    # 4. Metrics Calculation
    equity_curve = np.array(equity_curve)
    returns = np.diff(equity_curve) / equity_curve[:-1]
    
    total_trades = accepted_count
    winning_trades = len([t for t in trades if t['pnl'] > 0])
    losing_trades = len([t for t in trades if t['pnl'] <= 0])
    
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
    
    gross_profit = sum([t['pnl'] for t in trades if t['pnl'] > 0])
    gross_loss = abs(sum([t['pnl'] for t in trades if t['pnl'] < 0]))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.9
    
    # Sharpe Ratio (Assuming Daily risk-free = 0 for simplicity)
    # We have trade-by-trade returns. We need to aggregate to Daily for standard Sharpe?
    # Or simplified Sharpe per trade? Let's do Trade-based Sharpe for granualrity then annualized loosely.
    avg_return = np.mean(returns) if len(returns) > 0 else 0
    std_return = np.std(returns) if len(returns) > 0 else 1
    sharpe_trade = avg_return / std_return if std_return > 0 else 0
    # Annualized Sharpe (approximate, assuming ~1000 trades/year? No, let's just show Trade Sharpe)
    
    # Drawdown
    peak = equity_curve[0]
    max_dd_amount = 0
    max_dd_percent = 0
    
    for val in equity_curve:
        if val > peak: peak = val
        dd = peak - val
        dd_pct = (dd / peak) * 100
        if dd_pct > max_dd_percent: max_dd_percent = dd_pct
        if dd > max_dd_amount: max_dd_amount = dd

    total_return_pct = ((balance - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100

    # 5. Report
    print("\n" + "="*50)
    print("📊 1-YEAR HARMONIZED BACKTEST REPORT")
    print(f"   (Gatekeeper v2.0 + Runner v1.2)")
    print("="*50)
    print(f"{'Metric':<25} | {'Value':<15}")
    print("-" * 45)
    print(f"{'Initial Capital':<25} | ${INITIAL_CAPITAL:,.2f}")
    print(f"{'Final Balance':<25} | ${balance:,.2f}")
    print(f"{'Net Return':<25} | {total_return_pct:+.2f}%")
    print("-" * 45)
    print(f"{'Total Signals':<25} | {accepted_count + rejected_count}")
    print(f"{'Signals Rejected':<25} | {rejected_count} ({rejected_count/(accepted_count+rejected_count)*100:.1f}%)")
    print(f"{'Trades Executed':<25} | {accepted_count}")
    print("-" * 45)
    print(f"{'Win Rate':<25} | {win_rate:.2f}%")
    print(f"{'Profit Factor':<25} | {profit_factor:.2f}")
    print(f"{'Sharpe Ratio (Trade)':<25} | {sharpe_trade:.4f}")
    print(f"{'Max Drawdown':<25} | {max_dd_percent:.2f}%")
    print("="*50 + "\n")
    
    if max_dd_percent < 10.0 and profit_factor > 1.5:
        print("✅ SYSTEM STATUS: FTMO PASSED & HIGHLY PROFITABLE")
    elif profit_factor > 1.2:
        print("⚠️ SYSTEM STATUS: PROFITABLE BUT RISKY")
    else:
        print("❌ SYSTEM STATUS: FAILED")

if __name__ == "__main__":
    run_backtest()
