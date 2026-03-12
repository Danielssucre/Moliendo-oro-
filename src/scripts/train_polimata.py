import os
import sys
import pandas as pd
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import DQN
from stable_baselines3.common.vec_env import DummyVecEnv

# Ensure models dir
os.makedirs('models', exist_ok=True)

class PolimataEnv(gym.Env):
    """
    Polimata Multi-Strategy RL Environment.
    State: [Hour (0-23), Symbol_Index (0-N)]
    Action: 0=Skip, 1=ALFA, 2=EXPLORATION, 3=NEMESIS
    Reward: Actual historical PnL
    """
    def __init__(self, df):
        super(PolimataEnv, self).__init__()
        self.df = df.copy()
        
        # We need a predictable list of symbols
        self.symbols = sorted(self.df['symbol'].unique())
        self.symbol_to_idx = {sym: i for i, sym in enumerate(self.symbols)}
        self.df['symbol_idx'] = self.df['symbol'].map(self.symbol_to_idx)
        
        # Unique samples (hour, symbol)
        self.samples = self.df[['hour', 'symbol_idx']].drop_duplicates().values
        self.current_step = 0
        
        # State: Box(low=0, high=max, shape=(2,))
        self.observation_space = spaces.Box(
            low=np.array([0, 0]), 
            high=np.array([23, len(self.symbols)-1]), 
            dtype=np.float32
        )
        
        # Actions: 0=Skip, 1=ALFA, 2=EXPL, 3=NEME
        self.action_space = spaces.Discrete(4)
        
        # Precompute rewards dict for fast lookup: (hour, symbol_idx, block) -> avg_pnl
        self.rewards_map = {}
        grouped = self.df.groupby(['hour', 'symbol_idx', 'block'])['total_pnl'].mean().reset_index()
        for _, row in grouped.iterrows():
            if row['block'] == 'ALFA': act = 1
            elif row['block'] == 'EXPLORATION': act = 2
            elif row['block'] == 'NEMESIS': act = 3
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
        
        if action == 0: # SKIP
            reward = 0.0
        else: # Try Strategy
            # Look up reward
            key = (int(hour), int(sym_idx), action)
            if key in self.rewards_map:
                reward = self.rewards_map[key]
                # Slight penalty for just taking risk, helps prefer SKIP if PNL is marginal or negative
                if reward < 0: reward *= 1.2 # Punish losses harder
            else:
                # If no data for this strategy, penalize it slightly so it prefers SKIP or known data
                reward = -0.5
                
        self.current_step += 1
        done = self.current_step >= len(self.samples)
        
        # Normalize reward just slightly to help RL stability
        reward_norm = np.clip(reward / 100.0, -5.0, 5.0)
        
        return self._get_obs() if not done else np.zeros(2, dtype=np.float32), reward_norm, done, False, {}

def train_polimata():
    print("🚀 Iniciando Entrenamiento de Agente POLIMATA...")
    csv_path = '/tmp/analyzed_positions.csv'
    if not os.path.exists(csv_path):
        print("❌ Dataset not found.")
        return
        
    df = pd.read_csv(csv_path)
    
    # Validation filters to only use main blocks
    df = df[df['block'].isin(['ALFA', 'EXPLORATION', 'NEMESIS'])]
    
    if len(df) < 50:
        print("⚠️ Not enough data.")
        return
        
    print(f"📊 Cargados {len(df)} registros. Entrenando Polímata...")
    
    env = PolimataEnv(df)
    vec_env = DummyVecEnv([lambda: env])
    
    model = DQN(
        "MlpPolicy", 
        vec_env, 
        verbose=0,
        learning_rate=0.005,
        buffer_size=100000,
        learning_starts=1000,
        batch_size=128,
        gamma=0.99,
        target_update_interval=500,
        exploration_fraction=0.3,
        exploration_final_eps=0.01,
        device="cpu"
    )
    
    model.learn(total_timesteps=30000)
    
    model_path = "models/polimata_rl_v1.zip"
    model.save(model_path)
    print(f"✅ Agente POLIMATA entrenado y guardado en: {model_path}")
    
    # Test strategy over all samples
    print("\\n--- POLIMATA SUPREME STRATEGY EVALUATION ---")
    actions_map = {0: 'SKIP', 1: 'ALFA', 2: 'EXPL', 3: 'NEMESIS'}
    
    env.reset()
    total_reward = 0
    predictions_log = []
    
    for i in range(len(env.samples)):
        obs = env._get_obs()
        action, _ = model.predict(obs, deterministic=True)
        # Manually compute true reward to state reality
        hour, sym_idx = env.samples[i]
        sym = env.symbols[sym_idx]
        key = (int(hour), int(sym_idx), int(action))
        
        true_reward = 0.0
        if action != 0:
            if key in env.rewards_map:
                true_reward = env.rewards_map[key]
            
        total_reward += true_reward
        predictions_log.append({'hour': hour, 'symbol': sym, 'action': actions_map[int(action)], 'pnl': true_reward})
        
        env.current_step += 1
        
    results_df = pd.DataFrame(predictions_log)
    print(results_df.groupby(['hour', 'action']).agg({'pnl': 'sum'}).reset_index())
    print(f"\\n💰 Total Simulated PnL using Polímata: ${total_reward:.2f}")

if __name__ == "__main__":
    import warnings
    warnings.filterwarnings('ignore')
    train_polimata()
