import torch
import numpy as np
import os
from stable_baselines3 import DQN

class MFESniperManager:
    """
    Manages dynamic partial closes before the 1.3R rule using RL.
    Actions: 0: HOLD, 1: PARTIAL_CLOSE (+BE), 2: FULL_CLOSE
    """
    def __init__(self, model_path=None):
        if model_path is None:
            model_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 
                "models", "mfe_sniper_surgical_v2.zip"
            )
        self.model_path = model_path
        self.enabled = False
        
        if os.path.exists(model_path):
            try:
                self.model = DQN.load(model_path)
                self.enabled = True
                # print(f"🎯 MFE Sniper Loaded from {model_path}")
            except Exception as e:
                print(f"❌ Failed to load MFE Sniper model: {e}")
        else:
            print(f"⚠️ MFE Sniper Model not found at {model_path}.")

    def get_action(self, current_r, max_r, ema_slope, vol, atr_norm):
        """
        Returns the action index: 0=Hold, 1=Partial
        """
        if not self.enabled:
            return 0 # Default to HOLD if disabled
            
        state = np.array([current_r, max_r, ema_slope, vol, atr_norm], dtype=np.float32)
        action, _states = self.model.predict(state, deterministic=True)
        return int(action)

    def process_position(self, p, info, df_h1):
        """
        Inference for a live MT5 position.
        Returns: action_type ('HOLD', 'PARTIAL', 'FULL')
        """
        if not self.enabled: return "HOLD"
        
        # Calculate R metrics
        entry_p = p.price_open
        sl_p = p.sl
        point = info.point
        risk_pips = abs(entry_p - sl_p) / point if sl_p > 0 else 100.0
        
        current_pips = (p.price_current - entry_p) / point
        if p.type == 1: current_pips = -current_pips # SELL
        current_r = current_pips / risk_pips
        
        # Max R Estimation (Simple for inference)
        # In production we track this via history or comment, for now let's use p.profit
        # but the model needs R values.
        # Assume max_r = current_r for fresh bars or use high/low of current session
        max_r = max(current_r, 0) 
        # Indicators
        avg_price = (p.price_open + p.price_current) / 2
        atr_norm = (df_h1['atr'].iloc[-1] / avg_price) if avg_price > 0 else 0.001
        ema_9_slope = (df_h1['ema_9'].diff().rolling(3).mean().iloc[-1]) / df_h1['atr'].iloc[-1]
        vol = (df_h1['close'].pct_change().rolling(24).std() * 1000).iloc[-1]
        
        action_idx = self.get_action(current_r, max_r, ema_9_slope, vol, atr_norm)
        action_map = {0: "HOLD", 1: "PARTIAL"}
        return action_map.get(action_idx, "HOLD")
