import numpy as np
import logging

logger = logging.getLogger(__name__)

class BayesianBeliefEngine:
    """
    Capa de Razonamiento Bayesiano (Fase 21).
    Implementa el enfoque de actualización dinámica de creencias (Cox) 
    para cuantificar la convicción probabilística del sistema.
    """
    
    def __init__(self, prior_bullish=0.5):
        # Nuestra creencia inicial (Prior): 0.5 es neutral
        self.p_bullish = prior_bullish
        
        # Likelihoods calibrados y expandidos (Fase 22)
        # P(Evidencia | Hipótesis)
        self.likelihoods = {
            'HIVE_BUY': {
                'Bullish': 0.65, # Señal técnica optimista
                'Bearish': 0.35
            },
            'HIVE_SELL': {
                'Bullish': 0.35,
                'Bearish': 0.65
            },
            'ML_SAFE': { # ML indica bajo riesgo de Stop Hunt
                'Bullish': 0.75,
                'Bearish': 0.25
            },
            'ML_RISKY': { # ML indica alto riesgo
                'Bullish': 0.20,
                'Bearish': 0.80
            }
        }

    def update_belief(self, evidence_type):
        """
        Aplica el Teorema de Bayes:
        P(Bullish | Evidence) = [P(Evidence | Bullish) * P(Bullish)] / P(Evidence)
        """
        if evidence_type not in self.likelihoods:
            logger.warning(f"⚠️ Evidencia desconocida: {evidence_type}")
            return self.p_bullish

        # 1. Numerador: P(E|H) * P(H)
        p_e_given_bullish = self.likelihoods[evidence_type]['Bullish']
        p_e_given_bearish = self.likelihoods[evidence_type]['Bearish']
        
        prior = self.p_bullish
        numerator = p_e_given_bullish * prior
        
        # 2. Denominador (Probabilidad Total de la Evidencia): 
        # P(E) = P(E|H1)*P(H1) + P(E|H2)*P(H2)
        denominator = (p_e_given_bullish * prior) + (p_e_given_bearish * (1 - prior))
        
        if denominator == 0: return self.p_bullish

        # 3. Probabilidad Posterior
        new_p_bullish = numerator / denominator
        
        entropy = self.calculate_entropy_for_p(new_p_bullish)
        conviction = self.calculate_conviction_for_p(new_p_bullish)

        logger.info(f"🧠 [BAYES] Evidence: {evidence_type}")
        logger.info(f"   ├─ Prior P(Bullish): {prior:.4f}")
        logger.info(f"   ├─ Likelihood P(E|Bullish): {p_e_given_bullish:.4f}")
        logger.info(f"   ├─ Posterior P(Bullish|E): {new_p_bullish:.4f}")
        logger.info(f"   └─ Entropy: {entropy:.4f} | Conviction Factor: {conviction:.2f}x")
        
        self.p_bullish = new_p_bullish
        return self.p_bullish

    def calculate_entropy_for_p(self, p):
        if p <= 0 or p >= 1: return 0.0
        return - (p * np.log2(p) + (1 - p) * np.log2(1 - p))

    def calculate_conviction_for_p(self, p):
        entropy = self.calculate_entropy_for_p(p)
        conviction = 1.3 - (entropy * 0.6) 
        return max(0.7, min(1.3, conviction))

    def calculate_entropy(self):
        return self.calculate_entropy_for_p(self.p_bullish)

    def get_conviction_factor(self):
        """
        Retorna un factor de dimensionamiento basado en la entropía.
        Baja Entropía (Alta Convicción) -> Factor > 1.0
        Alta Entropía (Incertidumbre) -> Factor < 1.0
        """
        entropy = self.calculate_entropy()
        # Escalamiento simple: 1.0 es base, máx 1.3, mín 0.7
        # Cuanto menor la entropía, mayor la convicción.
        conviction = 1.3 - (entropy * 0.6) 
        return max(0.7, min(1.3, conviction))

    def reset_belief(self):
        self.p_bullish = 0.5
        logger.info("🔄 Bayesian Belief reset to neutral (0.5)")
