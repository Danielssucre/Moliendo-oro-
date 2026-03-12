import os
import sys
import pandas as pd
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import DQN
from stable_baselines3.common.vec_env import DummyVecEnv

# Ensure models dir
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.makedirs(os.path.join(PROJECT_ROOT, 'models'), exist_ok=True)

class PolimataEnv(gym.Env):
    def __init__(self, df):
        super(PolimataEnv, self).__init__()
        self.df = df.copy()
        
        self.symbols = sorted(self.df['symbol'].unique())
        self.symbol_to_idx = {sym: i for i, sym in enumerate(self.symbols)}
        self.df['symbol_idx'] = self.df['symbol'].map(self.symbol_to_idx)
        
        self.samples = self.df[['hour', 'symbol_idx']].drop_duplicates().values
        self.current_step = 0
        
        self.observation_space = spaces.Box(
            low=np.array([0, 0]), 
            high=np.array([23, len(self.symbols)-1]), 
            dtype=np.float32
        )
        
        self.action_space = spaces.Discrete(4)
        
        self.rewards_map = {}
        grouped = self.df.groupby(['hour', 'symbol_idx', 'block'])['total_pnl'].mean().reset_index()
        for _, row in grouped.iterrows():
            if row['block'] == 'ALFA': act = 1
            elif row['block'] == 'EXPLORATION': act = 2
            elif row['block'] == 'EXPL': act = 2
            elif row['block'] == 'NEMESIS': act = 3
            elif row['block'] == 'NEME': act = 3
            else: continue
            self.rewards_map[(int(row['hour']), int(row['symbol_idx']), act)] = row['total_pnl']
            
    def _get_obs(self):
        hour, sym_idx = self.samples[self.current_step]
        return np.array([hour, sym_idx], dtype=np.float32)

    def reset(self, **kwargs):
        self.current_step = 0
        return self._get_obs(), {}

    def step(self, action):
        hour, sym_idx = self.samples[self.current_step]
        
        if action == 0:
            reward = 0.0
        else:
            key = (int(hour), int(sym_idx), action)
            if key in self.rewards_map:
                reward = self.rewards_map[key]
                if reward < 0: reward *= 1.2
            else:
                reward = -0.5
                
        self.current_step += 1
        done = self.current_step >= len(self.samples)
        
        reward_norm = np.clip(reward / 100.0, -5.0, 5.0)
        
        return self._get_obs() if not done else np.zeros(2, dtype=np.float32), reward_norm, done, False, {}

def assimilate_data():
    paths = [
        os.path.join(PROJECT_ROOT, 'data/research/recent_ftmo_history.csv'),
        os.path.join(PROJECT_ROOT, 'data/research/shadow_grid_results.csv'),
        os.path.join(PROJECT_ROOT, 'data/research/analyzed_ftmo_history.csv')
    ]
    
    df_list = []
    
    for path in paths:
        if not os.path.exists(path):
            continue
            
        try:
            temp_df = pd.read_csv(path)
            if len(temp_df) == 0: continue
            
            # --- HOUR EXTRACTION ---
            if 'time' in temp_df.columns:
                # Handle unix vs iso
                first_val = temp_df['time'].iloc[0]
                if isinstance(first_val, (int, float, np.integer)):
                    temp_df['hour'] = pd.to_datetime(temp_df['time'], unit='s').dt.hour
                else:
                    temp_df['hour'] = pd.to_datetime(temp_df['time']).dt.hour
            elif 'position_id' in temp_df.columns:
                temp_df['hour'] = 12 # Fallback mid-day for legacy history
            else:
                temp_df['hour'] = 12
                
            # --- BLOCK EXTRACTION ---
            def extract_block(row):
                comment = ""
                for col in ['comment', 'comment_entry', 'config', 'strategy']:
                    if col in row and pd.notnull(row[col]):
                        comment += str(row[col])
                
                if 'ALFA' in comment: return 'ALFA'
                if 'EXPL' in comment: return 'EXPLORATION'
                if 'NEME' in comment: return 'NEMESIS'
                return 'UNKNOWN'
                
            temp_df['block'] = temp_df.apply(extract_block, axis=1)
            
            # --- PNL NORMALIZATION ---
            if 'profit' in temp_df.columns:
                temp_df['total_pnl'] = pd.to_numeric(temp_df['profit'], errors='coerce').fillna(0)
            elif 'outcome_r' in temp_df.columns:
                # Convert R to a $ value for scaling (assuming 1R ~ $20)
                temp_df['total_pnl'] = pd.to_numeric(temp_df['outcome_r'], errors='coerce').fillna(0) * 20.0
            else:
                temp_df['total_pnl'] = 0.0
                
            df_list.append(temp_df[['hour', 'symbol', 'block', 'total_pnl']])
            print(f"✅ Loaded {len(temp_df)} records from {os.path.basename(path)}")
            
        except Exception as e:
            print(f"⚠️ Error loading {path}: {e}")
            
    if not df_list:
        print("❌ No data to assimilate.")
        return None
        
    df = pd.concat(df_list, ignore_index=True)
    df = df[df['block'].isin(['ALFA', 'EXPLORATION', 'NEMESIS'])]
    # Normalize EXPLORATION vs EXPL
    df['block'] = df['block'].replace('EXPL', 'EXPLORATION')
    df['block'] = df['block'].replace('NEME', 'NEMESIS')
    
    return df

def retrain_polimata():
    df = assimilate_data()
    if df is None or len(df) < 10:
        print("⚠️ Not enough data.")
        return
        
    print(f"📊 Assimilating {len(df)} records...")
    env = PolimataEnv(df)
    vec_env = DummyVecEnv([lambda: env])
    
    model_path = os.path.join(PROJECT_ROOT, "models/polimata_rl_v1.zip")
    
    if os.path.exists(model_path):
        print("📥 Opening existing Polimata Neural Pathways...")
        try:
            model = DQN.load(model_path, env=vec_env)
            # Online Learning / Retraining without deleting memories
            print("🧠 Continuing education (Online Learning)...")
            model.learn(total_timesteps=20000, reset_num_timesteps=False)
        except ValueError as e:
            print(f"⚠️ Neural Architecture Mismatch: {e}")
            print("🔄 Scaling brain for new portfolio size... Training FRESH with combined data.")
            model = DQN("MlpPolicy", vec_env, verbose=0, learning_rate=0.002, buffer_size=100000, device="cpu")
            model.learn(total_timesteps=50000)
    else:
        print("⚠️ No existing model found. Training from scratch...")
        model = DQN("MlpPolicy", vec_env, verbose=0, learning_rate=0.002, buffer_size=100000, device="cpu")
        model.learn(total_timesteps=50000)
    
    model.save(model_path)
    print(f"✅ Agente POLIMATA actualizado.")

if __name__ == "__main__":
    import warnings
    warnings.filterwarnings('ignore')
    retrain_polimata()
