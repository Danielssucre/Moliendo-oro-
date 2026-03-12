import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd

class RiskSizingEnv(gym.Env):
    """
    Risk Sizing Environment: Learns optimal lot multipliers.
    State: [Signal_Prob, Current_DD, Volatility, ADX]
    Action: Discrete [0, 1, 2, 3, 4, 5] -> Map to [0.0, 0.5, 1.0, 1.5, 2.0, 2.5] multiplier
    Reward: Action * Outcome - (Drawdown_Penalty)
    """
    def __init__(self, csv_path, disciplined=False):
        super(RiskSizingEnv, self).__init__()
        self.df = pd.read_csv(csv_path)
        self.disciplined = disciplined
        self.current_step = 0
        
        # Action space: 6 discrete multiplier levels
        self.action_space = spaces.Discrete(6)
        self.multiplier_map = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
        
        # Observation: [prob, adx, rsi, vol, dd]
        self.observation_space = spaces.Box(low=0, high=100, shape=(5,), dtype=np.float32)
        
        self.reset()
        
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.balance = 10000.0
        self.peak = 10000.0
        self.dd = 0.0
        
        obs = self._get_obs()
        return obs, {}
        
    def _get_obs(self):
        row = self.df.iloc[self.current_step]
        # Normalize: prob (0-1), adx (0-100), rsi (0-100), vol (actual), dd (0.1)
        return np.array([
            row['prob'], 
            row['adx'], 
            row['rsi'], 
            row['vol'], 
            self.dd * 10.0 # Scaling DD for the net
        ], dtype=np.float32)
        
    def step(self, action):
        row = self.df.iloc[self.current_step]
        mult = self.multiplier_map[action]
        
        # Outcome in R-multiples (Base risk is 0.4%)
        base_risk_pct = 0.004
        trade_return_pct = mult * base_risk_pct * row['outcome_r']
        
        # Update Balance
        self.balance *= (1.0 + trade_return_pct)
        if self.balance > self.peak:
            self.peak = self.balance
        
        self.dd = (self.peak - self.balance) / self.peak
        
        # Reward Function: Aggressive Profit Capture
        reward = trade_return_pct * 1000.0  # Much higher incentive for profit
        
        # Disciplined Mode Enhancement: Harsh penalty for ANY loss
        if self.disciplined and trade_return_pct < 0:
            reward *= 20.0 # Extreme pain for a loss (Ultra-Disciplinarian)
            
        # Drawdown Penalty: Keep it but only for extreme cases (>5%)
        if self.dd > 0.05:
            reward -= (self.dd * 1000.0) ** 1.5 
            
        # L-H-N Beta Sniper Proposal: Strong penalization for ranging markets
        if mult > 0.0 and row['adx'] < 25.0:
            reward -= 5.0 # Stop hunting prevention
            
        # Penalty for trading on low probability
        prob_threshold = 0.75 if self.disciplined else 0.65
        if mult > 0.0 and row['prob'] < prob_threshold:
            reward -= 5.0 if self.disciplined else 2.0 
            
        # Small reward for surviving (Stability incentive)
        reward += 0.01 
            
        self.current_step += 1
        done = self.current_step >= len(self.df) - 1
        
        # Terminal penalty if account blown
        if self.balance < 5000:
            reward -= 1000
            done = True
            
        obs = self._get_obs()
        return obs, reward, done, False, {}
