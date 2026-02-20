
import numpy as np
import os
import logging

try:
    from stable_baselines3 import DQN
except ImportError:
    DQN = None

logger = logging.getLogger(__name__)

class AsymmetricRiskOracle:
    """
    Analyzes historical distribution of trades to determine safe lot sizes.
    Uses Reinforcement Learning (DQN) for dynamic optimization.
    """
    def __init__(self, fraction=0.20, max_mult=2.5, sample_size=1000, rl_model_path=None):
        self.fraction = fraction
        self.max_mult = max_mult
        self.sample_size = sample_size
        self.portfolio_max_heat = 0.05
        self.rl_models = {}
        self.global_rl_model = None
        
        if rl_model_path and DQN and os.path.exists(rl_model_path):
            try:
                self.global_rl_model = DQN.load(rl_model_path)
                logger.info(f"🧠 Global Quantum RL Risk Oracle loaded from {rl_model_path}")
            except Exception as e:
                logger.error(f"❌ Failed to load global RL model: {e}")

    def get_specialized_model(self, symbol):
        """Lazy load specialized model for a symbol."""
        if symbol in self.rl_models:
            return self.rl_models[symbol]
            
        model_path = f"models/risk_oracle_rl_{symbol}.zip"
        if os.path.exists(model_path) and DQN:
            try:
                self.rl_models[symbol] = DQN.load(model_path)
                logger.info(f"🎯 Specialized RL model loaded for {symbol}")
                return self.rl_models[symbol]
            except Exception as e:
                logger.error(f"❌ Error loading specialized model for {symbol}: {e}")
                
        return self.global_rl_model

    def calculate_sizing_multiplier(self, probability: float, reward_risk: float = 1.5, 
                                   current_dd: float = 0.0, exposure_heat: float = 0.0,
                                   adx: float = 25.0, rsi: float = 50.0, vol: float = 0.0,
                                   symbol: str = "GLOBAL"):
        """
        Calculates a multiplier for the base risk.
        Attempts to use specialized RL model first, then global, then math fallback.
        """
        # Try RL first
        model = self.get_specialized_model(symbol)
        
        if model:
            try:
                # Observation: [prob, adx, rsi, vol, dd] (scaled as in env)
                obs = np.array([probability, adx, rsi, vol, current_dd * 10.0], dtype=np.float32)
                action, _ = model.predict(obs, deterministic=True)
                # Map action back to multiplier [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
                mult_map = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
                rl_mult = mult_map[action]
                return rl_mult
            except Exception as e:
                logger.error(f"RL Prediction failed: {e}")

        # Math Fallback (Kelly-inspired)
        if probability < 0.55: return 0.0
        
        base_mult = (probability - (1-probability)/reward_risk) * self.max_mult
        
        # Drawdown Dampener
        dd_penalty = 1.0 - (current_dd * 5.0) # Reduces risk searchingly as DD increases
        multiplier = max(0.0, base_mult * dd_penalty)
        
        return min(multiplier, self.max_mult)

def calculate_portfolio_heat(mt5, symbol=None):
    """
    Calculates total risk exposure of the account in percentage.
    Uses Stop Loss distance to calculate R-multiple heat.
    """
    try:
        positions = mt5.positions_get()
        if not positions or len(positions) == 0:
            return 0.0
            
        total_risk_pct = 0.0
        acc = mt5.account_info()
        balance = float(acc.balance) if acc else 10000.0
        
        for pos in positions:
            if pos.sl > 0:
                # Calculate risk in money terms
                # Distance * Volume * TickValue/TickSize
                s_info = mt5.symbol_info(pos.symbol)
                if s_info:
                    risk_dist = abs(pos.open_price - pos.sl)
                    # Simple approximation if tick value is complex
                    risk_amt = (risk_dist / s_info.point) * s_info.trade_tick_value * pos.volume
                    total_risk_pct += (risk_amt / balance)
            else:
                # If no SL, we assume a 1.5% "logical" heat for the position
                total_risk_pct += 0.015
                
        return total_risk_pct
    except Exception as e:
        # Avoid crashing the loop if heat calculation fails
        return 0.0
