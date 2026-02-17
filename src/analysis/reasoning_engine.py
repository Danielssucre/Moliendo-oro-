"""
Reasoning Engine for the Manual Trading Assistant.
Translates technical metrics into human-readable market context.
"""
from typing import Dict, List, Any
from ..utils.logger import logger

class ReasoningEngine:
    """
    Component that provides natural language explanations for trading signals.
    Follows institutional DSS (Decision Support System) principles.
    """
    
    def __init__(self):
        pass

    def generate_context(
        self, 
        trend_data: Dict, 
        indicators_h1: Dict, 
        indicators_h4: Dict,
        probability: float,
        monte_carlo_prob: float = None
    ) -> Dict[str, Any]:
        """
        Generates a human-readable analysis of the market state.
        """
        analysis = []
        warnings = []
        strengths = []
        
        # 1. Trend Context
        consensus = trend_data.get('consensus', 'neutral')
        d1_dir = trend_data.get('timeframes', {}).get('long', {}).direction if trend_data.get('timeframes', {}).get('long') else 'unknown'
        h4_dir = trend_data.get('timeframes', {}).get('medium', {}).direction if trend_data.get('timeframes', {}).get('medium') else 'unknown'
        
        if consensus == 'bullish':
            strengths.append("Estructura alcista confirmada en múltiples temporalidades.")
        elif consensus == 'bearish':
            strengths.append("Dominancia bajista clara con alineación de tendencias.")
        else:
            analysis.append("El mercado se encuentra en una fase lateral o de transición (Consenso Neutral).")

        # 2. Indicator Interpretation
        adx = indicators_h4.get('adx', 0)
        rsi = indicators_h1.get('rsi', 50)
        
        if adx > 25:
            analysis.append(f"Fuerza de tendencia sólida (ADX: {adx:.1f}). Los breakouts tienen mayor probabilidad de éxito.")
        else:
            warnings.append(f"Tendencia débil (ADX: {adx:.1f}). Existe riesgo de 'whipsaws' o falsos movimientos.")

        if rsi > 70:
            warnings.append(f"RSI en zona de sobrecompra ({rsi:.1f}). Considerar toma de ganancias o esperar retroceso.")
        elif rsi < 30:
            warnings.append(f"RSI en zona de sobreventa ({rsi:.1f}). Posibilidad de rebote técnico inminente.")
        else:
            analysis.append(f"RSI estable ({rsi:.1f}), permitiendo continuidad del movimiento actual.")

        # 3. Probability & Reliability
        analysis.append(f"Confianza del sistema: {probability:.1%}.")
        if monte_carlo_prob:
            analysis.append(f"Validación estadística (Monte Carlo): {monte_carlo_prob:.1%}.")

        return {
            "narrative": analysis,
            "strengths": strengths,
            "warnings": warnings,
            "summary": self._generate_one_liner(consensus, adx, probability)
        }

    def _generate_one_liner(self, consensus: str, adx: float, prob: float) -> str:
        """Generates a quick summary for the trader."""
        if prob > 0.7 and adx > 25:
            return f"Oportunidad de ALTA CONFIANZA ({consensus.upper()}). Mercado con inercia favorable."
        if prob > 0.6:
            return f"Señal moderada ({consensus}). Requiere confirmación manual del trader."
        return "Baja convicción. Se recomienda modo observación."
