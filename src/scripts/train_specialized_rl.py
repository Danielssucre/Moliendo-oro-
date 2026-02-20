
import os
import sys
import pandas as pd
import numpy as np
from stable_baselines3 import DQN
from stable_baselines3.common.vec_env import DummyVecEnv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nanobot.ml.risk_env import RiskSizingEnv

def train_specialized_agent(symbol, csv_path=None, disciplined=False):
    print(f"🚀 Starting Specialized RL Training for {symbol}...")
    
    if not csv_path:
        csv_path = "data/research/risk_specialized_dataset.csv"
    
    if not os.path.exists(csv_path):
        print(f"❌ Dataset not found at {csv_path}")
        return

    # Load and filter dataset
    df = pd.read_csv(csv_path)
    # Filter by symbol if the dataset contains multiple, otherwise use all
    if 'symbol' in df.columns and len(df['symbol'].unique()) > 1:
        pair_df = df[df['symbol'] == symbol]
    else:
        pair_df = df
    
    if len(pair_df) < 50:
        print(f"⚠️ Not enough data for {symbol} ({len(pair_df)} signals). Need at least 50.")
        return

    # Save temporary pair dataset
    temp_csv = f"data/research/temp_risk_{symbol}.csv"
    pair_df.to_csv(temp_csv, index=False)

    try:
        # Create environment
        env = RiskSizingEnv(temp_csv, disciplined=disciplined)
        env = DummyVecEnv([lambda: env])

        # Initialize DQN Agent
        # Specialized for risk management: Small network is enough to prevent overfitting
        model = DQN(
            "MlpPolicy", 
            env, 
            verbose=1,
            learning_rate=1e-3,
            buffer_size=50000,
            learning_starts=1000,
            batch_size=64,
            gamma=0.99,
            target_update_interval=500,
            train_freq=4,
            gradient_steps=1,
            exploration_fraction=0.1,
            exploration_final_eps=0.05,
            device="cpu"
        )

        # Train
        # 50,000 steps for a specialized pair is robust
        train_steps = 50000
        print(f"🧠 Training {symbol} agent for {train_steps} steps...")
        model.learn(total_timesteps=train_steps)

        # Save model
        output_dir = "models"
        os.makedirs(output_dir, exist_ok=True)
        model_name = f"risk_oracle_rl_{symbol}.zip"
        model_path = os.path.join(output_dir, model_name)
        model.save(model_path)
        
        print(f"✅ Specialized Agent saved: {model_path}")

    finally:
        if os.path.exists(temp_csv):
            os.remove(temp_csv)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Train specialized RL risk agent for a pair")
    parser.add_argument("--symbol", type=str, required=True, help="Symbol to train (e.g. BTCUSD)")
    parser.add_argument("--csv", type=str, default=None, help="Path to specialized dataset CSV")
    parser.add_argument("--disciplined", action="store_true", help="Use disciplined mode (heavy loss penalty)")
    args = parser.parse_args()
    
    train_specialized_agent(args.symbol, csv_path=args.csv, disciplined=args.disciplined)
