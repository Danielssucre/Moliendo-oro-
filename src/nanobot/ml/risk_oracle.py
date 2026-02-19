import numpy as np
import os
try:
    from stable_baselines3 import DQN
except ImportError:
    DQN = None

try:
    from ..utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class AsymmetricRiskOracle:
    """
    Quantum Risk Oracle: Optimized Capital Allocation.
    Uses non-linear probability scaling and portfolio heat management.
    """
    
    def __init__(self, fraction=0.20, max_mult=2.5, sample_size=1000, rl_model_path=None):
        self.fraction = fraction
        self.max_mult = max_mult
        self.n = sample_size
        self.portfolio_max_heat = 0.05 # Max 5% total risk open
        self.rl_model = None
        
        if rl_model_path and DQN and os.path.exists(rl_model_path):
            try:
                self.rl_model = DQN.load(rl_model_path)
                logger.info(f"🧠 Quantum RL Risk Oracle loaded from {rl_model_path}")
            except Exception as e:
                logger.error(f"⚠️ Failed to load RL Risk Model: {e}")

    def calculate_sizing_multiplier(self, probability: float, reward_risk: float = 1.5, 
                                   current_dd: float = 0.0, exposure_heat: float = 0.0,
                                   adx=20, rsi=50, vol=1.0) -> float:
        """
        Unified method that uses RL if available, else falls back to mathematical asym sizing.
        """
        if self.rl_model:
            return self.calculate_rl_sizing(probability, adx, rsi, vol, current_dd)
        return self.calculate_asymmetric_sizing(probability, reward_risk, current_dd, exposure_heat)

    def calculate_rl_sizing(self, prob: float, adx: float, rsi: float, vol: float, dd: float) -> float:
        """
        Uses the trained DQN agent for lot sizing.
        """
        if not self.rl_model:
            return 1.0
            
        try:
            # Multiplier levels map
            mult_map = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
            # State: [prob, adx, rsi, vol, dd*10]
            obs = np.array([prob, adx, rsi, vol, dd * 10.0], dtype=np.float32)
            action, _ = self.rl_model.predict(obs, deterministic=True)
            multiplier = mult_map[action]
            
            logger.info(f"🧠 [RISK RL] Action={action} | Mult={multiplier}x | Obs: p={prob:.2f} dd={dd:.2f}")
            return multiplier
        except Exception as e:
            logger.error(f"⚠️ RL Prediction Error: {e}")
            return 1.0
            
    def calculate_asymmetric_sizing(self, probability: float, reward_risk: float = 1.5, 
                                   current_dd: float = 0.0, exposure_heat: float = 0.0) -> float:
        """
        Mathematical fallback for lot sizing.
        """
        p = probability
        q = 1.0 - p
        b = reward_risk
        
        p_scaled = p ** 3 
        dd_penalty = max(0.2, 1.0 - (current_dd * 10)) 
        active_fraction = self.fraction * dd_penalty
        
        f_star = (b * p - q) / b
        if f_star <= 0:
            return 0.0 
            
        heat_factor = max(0.0, 1.0 - (exposure_heat / self.portfolio_max_heat))
        f_adj = active_fraction * f_star * p_scaled * heat_factor
        multiplier = 0.8 + (f_adj * 15.0) 
        
        final_mult = max(0.0, min(self.max_mult, multiplier))
        logger.info(f"🏦 [RISK MATH] p={p:.2f} | f*={f_star:.2f} | Heat={exposure_heat:.1%} | FINAL_MULT={final_mult:.2f}x")
        
        return final_mult

def calculate_portfolio_heat(mt5_client, info_dummy=None):
    """
    Calculates total active risk (R) relative to equity.
    """
    try:
        positions = mt5_client.positions_get()
        acc = mt5_client.account_info()
        if not positions or not acc: return 0.0
        
        equity = float(acc.equity)
        total_risk_usd = 0.0
        
        for p in positions:
            symbol = p.symbol
            sym_info = mt5_client.symbol_info(symbol)
            if not sym_info: continue
            
            entry = p.price_open
            sl = p.sl
            if sl == 0: 
                total_risk_usd += (equity * 0.01)
                continue 
            
            risk_per_unit = abs(entry - sl)
            total_risk_usd += p.volume * sym_info.trade_contract_size * risk_per_unit
            
        heat = total_risk_usd / equity
        return heat
    except Exception as e:
        logger.error(f"⚠️ Heat Calculation Error: {e}")
        return 0.0
