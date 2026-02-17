import numpy as np
from .utils.logger import logger

class KellyBeliefEngine:
    """
    Institutional Capital Allocation based on Fractional Kelly.
    Replaces simple entropy-based sizing with mathematical expectation.
    """
    
    def __init__(self, fraction=0.25, min_mult=0.0, max_mult=2.5, sample_size=894):
        self.fraction = fraction
        self.min_mult = min_mult
        self.max_mult = max_mult
        self.n = sample_size
        
    def calculate_sizing_multiplier(self, probability: float, reward_risk: float = 1.5, current_dd: float = 0.0) -> float:
        """
        Implementación Institucional de Kelly con Risk Overlay:
        1. SE (Standard Error) = sqrt(p*q/n)
        2. Shrinkage dinámico: alpha = alpha_base * (1 - SE/p)
        3. Risk Overlay: If DD > 3%, reduce fraction by 50%.
        4. Skip policy: if f* <= 0, size = 0.
        """
        p = probability
        q = 1.0 - p
        b = reward_risk
        
        # 0. Risk Overlay: Institutional protection during drawdowns
        active_fraction = self.fraction
        if current_dd > 0.03:
            active_fraction = self.fraction * 0.5
            logger.warning(f"🛡️ [KELLY OVERLAY] DD={current_dd:.2%}. Reducing fraction to {active_fraction:.3f}")
        
        # 1. Standard Error of the p estimate
        se = np.sqrt((p * q) / self.n) if self.n > 0 else 0.5
        
        # 2. Dynamic alpha adjustment based on uncertainty
        # If uncertainty is high relative to p, we shrink more.
        uncertainty_factor = max(0.0, 1.0 - (se / (p + 1e-6)))
        effective_alpha = active_fraction * uncertainty_factor
        
        # 3. Raw Kelly f*
        f_star = (b * p - q) / b
        
        # 4. Final Sizing Logic
        if f_star <= 0:
            logger.warning(f"⚖️ [KELLY] NEGATIVE EDGE: f*={f_star:.4f}. RECOMMEND SKIP.")
            return 0.0 # Strict Skip Policy

        # Apply Adjusted Fractional Kelly
        f_adj = effective_alpha * f_star
        
        # Multiplier calculation:
        # We want the multiplier to scale the BASE RISK (e.g. 0.4%).
        # Institutional Cap: Multiplier such that risk never exceeds e.g. 1.25%.
        # Risk_applied = Base_Risk * Multiplier
        # If Base_Risk is 0.4%, and we want Max 1.2%, Max Multiplier is 3.0.
        # However, 2.5x is a safer Institutional Guardrail.
        multiplier = 1.0 + (f_adj * 10.0) # Scaling f_adj (which is small) to multiplier space
        
        final_mult = max(self.min_mult, min(self.max_mult, multiplier))
        
        logger.info(f"⚖️ [KELLY] p={p:.3f} (SE={se:.3f}) | f*={f_star:.4f} | Alpha_Eff={effective_alpha:.3f} | Mult={final_mult:.2f}x")
        
        return final_mult

class BayesianEnsemble:
    """
    Fase 23: Ensemble of RF + Technical Evidence.
    """
    def __init__(self, prior=0.5):
        self.p_bullish = prior
        # Likelihoods derived fromconfusion matrix logic (Conceptual for now)
        self.likelihoods = {
            'RF_SAFE': {'Bullish': 0.75, 'Bearish': 0.25},
            'RF_TRAP': {'Bullish': 0.20, 'Bearish': 0.80}
        }
    
    def update(self, evidence_type):
        # Standard Bayes update
        p_h = self.p_bullish
        p_e_h = self.likelihoods[evidence_type]['Bullish']
        p_e_not_h = self.likelihoods[evidence_type]['Bearish']
        
        numerator = p_e_h * p_h
        denominator = (p_e_h * p_h) + (p_e_not_h * (1 - p_h))
        
        if denominator == 0: return p_h
        self.p_bullish = numerator / denominator
        return self.p_bullish
