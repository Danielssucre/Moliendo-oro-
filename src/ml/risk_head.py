import numpy as np
from scipy.stats import beta

class FTMOSafetyGuard:
    """
    Deterministic Circuit Breaker for FTMO Rules.
    Acts as the 'cold-blooded' enforcer that overrides all AI signals if limits are hit.
    """
    def __init__(self, initial_balance=10000, daily_loss_limit=150, max_drawdown=1000, profit_target=500):
        self.initial_balance = initial_balance
        self.daily_loss_limit = daily_loss_limit # 5% for FTMO usually
        self.max_drawdown = max_drawdown # 10% total
        self.profit_target = profit_target
        
    def check_safety(self, current_equity, daily_pnl):
        """
        Returns (is_safe, reason)
        """
        # 1. Daily Loss Limit
        if daily_pnl <= -self.daily_loss_limit:
            return False, f"CIRCUIT BREAKER: Daily Loss Limit hit (${daily_pnl:.2f})"
        
        # 2. Max Total Drawdown
        total_dd = self.initial_balance - current_equity
        if total_dd >= self.max_drawdown:
            return False, f"CIRCUIT BREAKER: Max Drawdown hit (${total_dd:.2f})"
            
        # 3. Daily Profit Target reached? (Discipline)
        if daily_pnl >= self.profit_target:
            return False, f"DISCIPLINE: Daily Profit Target reached (${daily_pnl:.2f}). Walking away."
            
        return True, "All safety protocols green."

class RiskHead:
    """
    Bayesian Risk Head with Entropy Gating and FTMO Safety Guard.
    """
    
    def __init__(self, entropy_threshold=0.8, initial_balance=10000):
        self.entropy_threshold = entropy_threshold
        self.safety_guard = FTMOSafetyGuard(initial_balance=initial_balance)
        # Bayesian Prior
        self.prior_alpha = 2
        self.prior_beta = 5
        self.successes = 0
        self.trials = 0

    def calculate_entropy(self, probabilities):
        """
        Calculates Shannon Entropy for a set of event probabilities.
        H = -sum(p * log2(p))
        """
        probs = np.array(probabilities)
        probs = probs / np.sum(probs)
        probs = np.clip(probs, 1e-9, 1.0)
        entropy = -np.sum(probs * np.log2(probs))
        return entropy

    def get_market_regime_prob(self):
        """
        Infers the probability of being in a 'Favorable' regime.
        """
        a = self.prior_alpha + self.successes
        b = self.prior_beta + (self.trials - self.successes)
        if a + b > 2:
            return (a - 1) / (a + b - 2)
        return a / (a + b)

    def validate_signal(self, expectancy, volatility_z_score, current_equity=10000, daily_pnl=0):
        """
        Validates signal with 3 layers:
        1. FTMO Safety (Deterministic)
        2. Bayesian Regime (Contextual)
        3. Shannon Entropy (Probabilistic)
        """
        # Layer 1: Deterministic Safety (The Cold-Blooded Enforcer)
        is_safe, safety_reason = self.safety_guard.check_safety(current_equity, daily_pnl)
        if not is_safe:
            return {
                "is_valid": False,
                "reason": safety_reason,
                "entropy": 1.0,
                "gt_score": 0.0
            }

        # Layer 2: Regime Check
        regime_prob = self.get_market_regime_prob()
        
        # Layer 3: Entropy Check (Shannon)
        base_p = np.clip(regime_prob, 0.01, 0.99)
        market_uncertainty = self.calculate_entropy([base_p, 1-base_p])
        noise_factor = np.clip(abs(volatility_z_score) / 3.0, 0, 1)
        total_entropy = (market_uncertainty * 0.5) + (noise_factor * 0.5)
        
        # GT-Score (Golden Ticket)
        gt_score = expectancy * regime_prob * (1.0 - total_entropy)
        
        is_valid = total_entropy < self.entropy_threshold
        reason = None
        if not is_valid:
            reason = f"VETO: Market entropy ({total_entropy:.2f}) too high"
        elif gt_score < 0.2:
            is_valid = False
            reason = "VETO: GT-Score below minimum threshold"
            
        return {
            "is_valid": is_valid,
            "reason": reason,
            "entropy": total_entropy,
            "gt_score": gt_score,
            "regime_prob": regime_prob
        }

    def record_result(self, is_win):
        """Update the Bayesian prior with trade results."""
        self.trials += 1
        if is_win:
            self.successes += 1
        if self.trials > 50:
            self.trials = 50
            self.successes = int(self.successes * 0.9)
