import os
import sys
import pickle
import torch
import numpy as np
import pandas as pd
from datetime import datetime

# Add project modules to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.ml.execution_head import ExecutionHead
from src.ml.risk_head import RiskHead

CACHE_FILE = "data/historical/bt_cache_60d.pkl"
MODEL_PATH = "data/cache/execution_head_v1.pth"
SEQ_LEN = 20

def prepare_data(data_dict):
    """
    Converts raw OHLC cache into training sequences.
    Features: [Normalized OHLC, Relative EMAs, ATR, TimeEnc]
    """
    X, Y = [], []
    
    for pair, df in data_dict.items():
        print(f"📦 Processing {pair}...")
        df = df.copy()
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Calculate Features
        df['ema_9'] = df['close'].ewm(span=9).mean()
        df['ema_200'] = df['close'].ewm(span=200).mean()
        df['atr'] = (df['high'] - df['low']).rolling(14).mean()
        
        # Targets (R-multiples)
        # We simulate a 1:3 RR trade starting at each bar
        df['target'] = 0.0
        for i in range(len(df) - 48):
            entry = df.iloc[i]['close']
            sl_dist = df.iloc[i]['atr'] * 1.5
            tp_dist = sl_dist * 3.0
            
            if sl_dist == 0 or pd.isna(sl_dist): continue
            
            # Simple simulation
            outcome = 0
            # Check Long
            sl, tp = entry - sl_dist, entry + tp_dist
            for j in range(i+1, i+48):
                f = df.iloc[j]
                if f['low'] <= sl: 
                    outcome = -1.0
                    break
                if f['high'] >= tp:
                    outcome = 3.0
                    break
            df.at[df.index[i], 'target'] = outcome

        # Normalize Features
        df['c_norm'] = df['close'] / df['close'].rolling(100).mean()
        df['ema9_rel'] = df['ema_9'] / df['close']
        df['ema200_rel'] = df['ema_200'] / df['close']
        df['atr_norm'] = df['atr'] / df['close']
        df['high_rel'] = df['high'] / df['close']
        df['low_rel'] = df['low'] / df['close']
        
        # Time Encoding
        df['hour'] = df['time'].dt.hour
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        df['day'] = df['time'].dt.dayofweek
        df['day_sin'] = np.sin(2 * np.pi * df['day'] / 7)
        df['day_cos'] = np.cos(2 * np.pi * df['day'] / 7)
        
        feature_cols = [
            'c_norm', 'ema9_rel', 'ema200_rel', 'atr_norm', 
            'high_rel', 'low_rel', 'hour_sin', 'hour_cos', 
            'day_sin', 'day_cos'
        ]
        
        features = df[feature_cols].bfill().fillna(0).values
        targets = df['target'].values
        
        for i in range(len(features) - SEQ_LEN):
            X.append(features[i:i+SEQ_LEN])
            Y.append(targets[i+SEQ_LEN-1])
            
    return torch.tensor(np.array(X), dtype=torch.float32), torch.tensor(np.array(Y), dtype=torch.float32).view(-1, 1)

def train():
    print("🚀 Starting Dual Head Training...")
    
    if not os.path.exists(CACHE_FILE):
        print("❌ Cache missing.")
        return

    with open(CACHE_FILE, 'rb') as f:
        data = pickle.load(f)

    X, Y = prepare_data(data)
    print(f"✅ Prepared {len(X)} sequences.")

    head = ExecutionHead()
    epochs = 5
    batch_size = 64
    
    for epoch in range(epochs):
        perm = torch.randperm(X.size(0))
        epoch_loss = 0
        for i in range(0, X.size(0), batch_size):
            indices = perm[i:i + batch_size]
            batch_x, batch_y = X[indices], Y[indices]
            
            loss = head.train_step(batch_x, batch_y)
            epoch_loss += loss
            
        print(f"📈 Epoch {epoch+1}/{epochs} | Loss: {epoch_loss/(len(X)/batch_size):.4f}")

    # Save
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    torch.save(head.model.state_dict(), MODEL_PATH)
    print(f"✨ Model saved to {MODEL_PATH}")

if __name__ == "__main__":
    train()
