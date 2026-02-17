import os
import torch
import torch.nn as nn
import numpy as np
import logging
import pandas as pd
from datetime import datetime

logger = logging.getLogger("NAANOBOT_RL")

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

class RLTrailingManager:
    """
    Manages the Infinite Runner phase using a Reinforcement Learning policy.
    Actions: 0: HOLD, 1: MOVE STOP (+0.5R), 2: CLOSE
    """
    def __init__(self, model_path=None, state_dim=6, action_dim=3):
        if model_path is None:
            model_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 
                "models", "infinite_rl_qnet_v1.pth"
            )
        self.model_path = model_path
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.q_net = QNetwork(state_dim, action_dim)
        self.enabled = False
        
        if os.path.exists(model_path):
            try:
                self.q_net.load_state_dict(torch.load(model_path))
                self.q_net.eval()
                self.enabled = True
                logger.info(f"🤖 RL Trailing Manager: Model loaded from {model_path}")
            except Exception as e:
                logger.error(f"❌ Failed to load RL model: {e}")
        else:
            logger.warning(f"⚠️ RL Model not found at {model_path}. RL Trailing disabled.")

    def get_action(self, current_r, max_r, ema_9_slope, vol, atr_norm, current_sl_r):
        """
        Returns the action index: 0=Hold, 1=Move, 2=Close
        """
        if not self.enabled:
            return 0 # Default to HOLD if disabled
            
        state = np.array([
            current_r,
            max_r,
            ema_9_slope,
            vol,
            atr_norm,
            current_sl_r
        ], dtype=np.float32)
        
        with torch.no_grad():
            state_t = torch.FloatTensor(state).unsqueeze(0)
            action = self.q_net(state_t).argmax().item()
            
        return action

    def process_position(self, p, info, df_h1):
        """
        Live processing of an MT5 position.
        Returns: action_type ('HOLD', 'MOVE', 'CLOSE')
        """
        if not self.enabled:
            return "HOLD"
            
        # 1. Calculate Real-time metrics
        entry_p = p.price_open
        sl_p = p.sl
        risk_pips = abs(entry_p - sl_p) / info.point if sl_p > 0 else (p.price_current * 0.002 / info.point) # Fallback
        
        # Protect against zero risk_pips
        if risk_pips == 0: risk_pips = 1.0 
        
        current_pips = (p.price_current - entry_p) / info.point
        if p.type == 1: # SELL
            current_pips = -current_pips
            
        current_r = current_pips / risk_pips
        
        # Max R tracking (needs persistent storage or use p.comment / p.profit_max if available)
        # For now, we'll estimate Max R from recent H1 high/low
        if p.type == 0: # BUY
            max_price = df_h1['high'].iloc[-24:].max() # Last 24 hours
            max_pips = (max_price - entry_p) / info.point
        else:
            max_price = df_h1['low'].iloc[-24:].min()
            max_pips = (entry_p - max_price) / info.point
            
        max_r_est = max_pips / risk_pips
        
        # Indicators
        ema_9 = df_h1['close'].ewm(span=9, adjust=False).mean()
        ema_9_slope = ema_9.diff(3).iloc[-1]
        
        # Current SL R
        current_sl_r = (abs(sl_p - entry_p) / info.point) / risk_pips if sl_p != entry_p else 0
        if p.type == 0 and sl_p < entry_p: current_sl_r = -current_sl_r # In loss or BE
        if p.type == 1 and sl_p > entry_p: current_sl_r = -current_sl_r
        
        atr = df_h1['atr'].iloc[-1] if 'atr' in df_h1.columns else (p.price_current * 0.002)
        vol = (df_h1['close'].pct_change().rolling(24).std() * 1000).iloc[-1]
        
        action_idx = self.get_action(
            current_r=current_r,
            max_r=max_r_est,
            ema_9_slope=ema_9_slope / atr if atr > 0 else 0,
            vol=vol,
            atr_norm=atr / p.price_current if p.price_current > 0 else 0,
            current_sl_r=current_sl_r
        )
        
        action_map = {0: "HOLD", 1: "MOVE", 2: "CLOSE"}
        return action_map.get(action_idx, "HOLD")
