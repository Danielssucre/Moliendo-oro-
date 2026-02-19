import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd

class PartialEnv(gym.Env):
    """
    Environment to simulate trade management before partial close.
    States: current_r, max_r, min_r, step_index, direction, volatility
    Actions: 0: HOLD, 1: PARTIAL_CLOSE (+BE), 2: FULL_CLOSE
    """
    def __init__(self, dataset_path):
        super(PartialEnv, self).__init__()
        self.df = pd.read_csv(dataset_path)
        self.trade_ids = self.df['trade_id'].unique()
        
        # Action space: 0=Hold, 1=Partial, 2=Full
        self.action_space = spaces.Discrete(3)
        
        # Observation space: [current_r, max_r, min_r, step, vol]
        self.observation_space = spaces.Box(low=-5, high=10, shape=(5,), dtype=np.float32)
        
        self.current_trade_idx = 0
        self.current_step = 0
        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        # Select random trade from dataset
        self.trade_id = np.random.choice(self.trade_ids)
        self.trade_data = self.df[self.df['trade_id'] == self.trade_id].reset_index(drop=True)
        self.current_step = 0
        
        obs = self._get_obs()
        return obs, {}

    def _get_obs(self):
        row = self.trade_data.iloc[self.current_step]
        return np.array([
            row['current_r'],
            row['max_r'],
            row['min_r'],
            row['hour_of_trade'],
            row['volatility']
        ], dtype=np.float32)

    def step(self, action):
        row = self.trade_data.iloc[self.current_step]
        done = False
        truncated = False
        reward = 0
        
        # Check for natural termination (SL or Max TP)
        if row['is_terminal'] == 1:
            reward = row['current_r'] if row['current_r'] > 0 else -1.0
            # Penalty for inefficiency
            if row['max_r'] > row['current_r']:
                reward -= (row['max_r'] - row['current_r']) * 0.3
            done = True
            return self._get_obs(), reward, done, truncated, {}

        if action == 1: # PARTIAL_CLOSE
            # Reward: Capture efficiency at this moment
            reward = row['current_r']
            # Bonus if we are > 1R
            if row['current_r'] >= 1.0: reward += 0.2
            done = True
        elif action == 2: # FULL_CLOSE
            reward = row['current_r']
            # Small penalty for closing full too early if trend is strong
            if row['current_r'] < 1.0: reward -= 0.1
            done = True
        else: # HOLD
            self.current_step += 1
            if self.current_step >= len(self.trade_data) - 1:
                reward = row['current_r']
                done = True
            else:
                reward = 0 # No immediate reward for holding
        
        obs = self._get_obs() if not done else np.zeros((5,), dtype=np.float32)
        return obs, reward, done, truncated, {}

if __name__ == "__main__":
    # Test environment
    env = PartialEnv("data/research/mfe_dataset_v1.csv")
    obs, _ = env.reset()
    print(f"Initial Obs: {obs}")
    obs, rew, done, _, _ = env.step(0)
    print(f"Step 1 (Hold) -> Obs: {obs}, Rew: {rew}, Done: {done}")
