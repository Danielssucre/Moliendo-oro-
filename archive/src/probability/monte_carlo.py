"""
Monte Carlo Validator - Simulación de caminos de precio para validación de señales.
"""
import numpy as np
from typing import Dict, Tuple

from ..utils.logger import logger
from ..utils.config import config

class MonteCarloValidator:
    """
    Validador estadístico basado en simulaciones de Monte Carlo.
    Estima la probabilidad de que el precio toque el TP antes que el SL
    basado en la volatilidad actual (ATR).
    """
    
    def __init__(self, num_simulations: int = 1000, steps: int = 48):
        """
        Args:
            num_simulations: Número de trayectorias a simular
            steps: Número de pasos (velas H1) en el futuro
        """
        self.num_simulations = num_simulations
        self.steps = steps

    def validate_signal(
        self,
        entry: float,
        tp: float,
        sl: float,
        atr: float,
        direction: str,
        trend_strength: float = 0
    ) -> Tuple[float, bool]:
        """
        Ejecuta la simulación y retorna la probabilidad de éxito.
        
        Args:
            entry: Precio de entrada
            tp: Take Profit
            sl: Stop Loss
            atr: Valor ATR actual (volatilidad)
            direction: "BUY" o "SELL"
            trend_strength: Fuerza de la tendencia (0-100, usualmente ADX)
            
        Returns:
            (probabilidad_exito, pasa_filtro)
        """
        logger.progress(f"Ejecutando simulación Monte Carlo ({self.num_simulations} caminos)")
        
        # El ATR representa el rango promedio. Lo usamos como base para la volatilidad.
        std_dev = atr * 0.4
        
        # El "drift" (sesgo) se basa en la fuerza de la tendencia.
        # Si ADX=50, asumimos un drift total de 0.5 * ATR en el periodo.
        total_drift = (trend_strength / 100) * atr * (1.0 if direction.upper() == "BUY" else -1.0)
        drift_per_step = total_drift / self.steps
        
        # Generar retornos aleatorios (Normal) + Drift
        random_walks = np.random.normal(drift_per_step, std_dev, (self.num_simulations, self.steps))
        
        # Calcular trayectorias de precios
        paths = entry + np.cumsum(random_walks, axis=1)
        
        win_count = 0
        
        for i in range(self.num_simulations):
            path = paths[i]
            
            if direction.upper() == "BUY":
                hit_sl = np.where(path <= sl)[0]
                hit_tp = np.where(path >= tp)[0]
            else: # SELL
                hit_sl = np.where(path >= sl)[0]
                hit_tp = np.where(path <= tp)[0]
            
            idx_sl = hit_sl[0] if len(hit_sl) > 0 else float('inf')
            idx_tp = hit_tp[0] if len(hit_tp) > 0 else float('inf')
            
            if idx_tp < idx_sl and idx_tp != float('inf'):
                win_count += 1
                
        probability = win_count / self.num_simulations
        
        # Umbral mínimo de probabilidad estadística
        # Para RR 1:2.5, el break-even aleatorio es 28%. 
        # Si el Monte Carlo con drift da > 45%, la probabilidad es muy alta.
        min_stat_prob = config.get_trading_config("probability.min_monte_carlo_prob") or 0.45
        passed = probability >= min_stat_prob
        
        logger.info(f"📊 Monte Carlo Win Prob (Base Drift): {probability:.1%} | {'PASÓ' if passed else 'FALLÓ'}")
        
        return probability, passed
