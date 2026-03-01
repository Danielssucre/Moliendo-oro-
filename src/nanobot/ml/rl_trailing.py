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

    def process_position(self, p, info, df_h1, mt5_client=None):
        """
        Live processing of an MT5 position.
        Returns: action_type ('HOLD', 'MOVE', 'CLOSE')
        """
        if not self.enabled:
            return "HOLD"
            
        # 1. Calculate Real-time metrics
        entry_p = p.price_open
        sl_p = p.sl
        tp_p = p.tp
        
        # Phase 4 Fix: Mathematical Stability for R-multiples
        # Use TP distance to deduce initial risk if SL has been moved to BE or Trailing.
        # Strategy: RR Target is 1.5, so Initial Risk = (TP Distance) / 1.5
        tp_dist_pips = abs(tp_p - entry_p) / info.point if tp_p > 0 else (p.price_current * 0.003 / info.point)
        initial_risk_pips = tp_dist_pips / 1.5
        
        # Stability check
        if initial_risk_pips < 1.0: initial_risk_pips = 10.0 # Standard fallback
        
        current_pips = (p.price_current - entry_p) / info.point
        if p.type == 1: # SELL
            current_pips = -current_pips
            
        current_r = current_pips / initial_risk_pips
        
        # True MFE tracking (Phase 4 Logic Hardening)
        # Using MT5 history since position opening time
        if hasattr(p, 'time_setup'):
            pos_time = datetime.fromtimestamp(p.time_setup)
            rates_since = mt5_client.copy_rates_from(p.symbol, mt5_client.TIMEFRAME_H1, pos_time, datetime.now())
            if rates_since is not None and len(rates_since) > 0:
                m_df = pd.DataFrame(rates_since)
                if p.type == 0: # BUY
                    max_price = m_df['high'].max()
                    max_pips = (max_price - entry_p) / info.point
                else: # SELL
                    max_price = m_df['low'].min()
                    max_pips = (entry_p - max_price) / info.point
            else:
                max_pips = current_pips
        else:
            max_pips = current_pips # Fallback
            
        max_r_est = max_pips / initial_risk_pips
        
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
