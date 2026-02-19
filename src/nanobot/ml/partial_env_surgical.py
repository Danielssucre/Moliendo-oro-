import gymnasium as gym
from gymnasium import spaces
import numpy as np
import json
import os

class PartialEnvSurgical(gym.Env):
    """
    Surgical Environment: Punishes closing trades that WOULD have hit the target.
    Rewards closing only if the trade was destined to reverse.
    """
    def __init__(self, json_path):
        super(PartialEnvSurgical, self).__init__()
        with open(json_path, 'r') as f:
            self.trade_data = json.load(f)
        
        # Action space: 0=Hold, 1=Partial/Close
        self.action_space = spaces.Discrete(2)
        
        # Observation space: [current_r, max_r, ema_slope, vol, atr_norm]
        self.observation_space = spaces.Box(low=-5, high=10, shape=(5,), dtype=np.float32)
        
        self.current_trade_idx = 0
        self.current_step = 0
        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        # Select random trade
        self.trade_idx = np.random.randint(0, len(self.trade_data))
        self.current_trade = self.trade_data[self.trade_idx]
        self.history = self.current_trade['history']
        
        # The ultimate potential of this trade
        self.max_r_final = self.current_trade.get('final_outcome_r', 
                                                 max([s['max_r'] for s in self.history]))
        
        self.current_step = 0
        obs = self._get_obs()
        return obs, {}

    def _get_obs(self):
        step_data = self.history[self.current_step]
        return np.array([
            step_data['current_r'],
            step_data['max_r'],
            step_data['ema_9_slope'],
            step_data['vol'],
            step_data.get('atr_norm', 0.001)
        ], dtype=np.float32)

    def step(self, action):
        step_data = self.history[self.current_step]
        done = False
        truncated = False
        reward = 0
        
        # ACTION: CLOSE (Partial)
        if action == 1:
            done = True
            # Surgical logic:
            if self.max_r_final >= 1.3:
                # Crime: We closed a trade that would have reached the 1.3R target!
                reward = -2.5 # Heavier penalty for being too early
            else:
                # Hero: We saved profit from a trade that would have reversed.
                if step_data['current_r'] > 0.5:
                    reward = step_data['current_r'] * 2.0 # Reward for saving significant profit
                elif step_data['current_r'] > 0:
                    reward = step_data['current_r']
                else:
                    reward = -0.1 # Closing in red before target is ok if it was going to touch SL

        # ACTION: HOLD
        else:
            self.current_step += 1
            if self.current_step >= len(self.history) - 1:
                # Trajectory ended naturally
                done = True
                if self.max_r_final >= 1.3:
                    reward = 1.3 # Success by holding!
                else:
                    reward = step_data['current_r'] # Outcome of holding
            else:
                reward = 0 

        obs = self._get_obs() if not done else np.zeros((5,), dtype=np.float32)
        return obs, reward, done, truncated, {}

if __name__ == "__main__":
    env = PartialEnvSurgical("data/research/rl_trajectories_v1.json")
    print(f"Loaded {len(env.trade_data)} trades.")
    obs, _ = env.reset()
    print(f"Initial Obs: {obs}, Final Max R: {env.max_r_final}")
