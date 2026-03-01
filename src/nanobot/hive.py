"""
Signal generation with complete trading information.
"""
from datetime import datetime, timedelta
from typing import Dict, Optional
from dataclasses import dataclass, asdict

from .risk_manager import RiskCalculator, RiskParameters
from .kelly_sizing import ProbabilityComponents # Temporary if we merge or keep as is
from ..utils.config import config
from ..utils.logger import logger


@dataclass
class TradingSignal:
    """Complete trading signal with all parameters."""
    # Basic info
    pair: str
    direction: str  # "BUY" or "SELL"
    timestamp: str
    
    # Entry and exits
    entry_price: float
    stop_loss: float
    take_profit: float
    
    # Risk management
    risk_pips: float
    reward_pips: float
    risk_reward_ratio: float
    position_size: float
    risk_amount: float
    
    # Probability and confidence
    probability: float
    monte_carlo_prob: float
    confidence_level: str  # "HIGH", "MEDIUM", "LOW"
    
    # Validity
    valid_until: str
    validity_hours: int
    
    # Justification
    trend_analysis: str
    entry_reason: str
    indicator_confirmations: list
    risk_justification: str
    
    # Additional context
    current_price: float
    atr_value: float
    
    # Reasoning Engine outputs (Manual Assistant)
    market_narrative: list = None
    strengths: list = None
    warnings: list = None

    # Default-valued fields MUST go last
    order_type: str = "MARKET"  # "MARKET", "LIMIT", "STOP"
    tp_targets: Optional[Dict[str, Dict[str, float]]] = None  # {"TP1": {"price": 0.0, "prob": 0.0}, ...}
    exposure_warning: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)
    
    def format_for_display(self) -> str:
        """Format signal for user display."""
        # Determine emoji based on direction
        emoji = "🟢" if self.direction == "BUY" else "🔴"
        
        output = f"""
🎯 SEÑAL LIMIT {self.direction} {self.pair}
{'='*50}

{emoji} Dirección: {self.direction}
📍 Entrada: {self.entry_price:.5f}
🛑 Stop Loss: {self.stop_loss:.5f} (riesgo: {self.risk_pips:.1f} pips)
🎯 Take Profit: {self.take_profit:.5f} (reward: {self.reward_pips:.1f} pips)

📊 Probabilidad (Kalman): {self.probability:.1%}
🎲 Monte Carlo Prob: {self.monte_carlo_prob:.1%}
⭐ Confianza: {self.confidence_level}
⏰ Válido hasta: {self.valid_until} ({self.validity_hours}h)

💰 Gestión de Riesgo:
   - Risk/Reward: 1:{self.risk_reward_ratio:.2f}
   - Tamaño posición: {self.position_size:.2f} lotes
   - Riesgo: ${self.risk_amount:.2f} ({config.get_trading_config('risk_management.max_risk_per_trade_percent')}% del capital)

🎯 OBJETIVOS DE PROFIT (TP):
{self._format_tp_targets()}

📈 Justificación:

1. Tendencia:
   {self.trend_analysis}

2. Razón de entrada:
   {self.entry_reason}

3. Confirmaciones de indicadores ({len(self.indicator_confirmations)}):
   {self._format_confirmations()}

4. Gestión de riesgo:
   {self.risk_justification}

📌 Contexto:
   - Precio actual: {self.current_price:.5f}
   - ATR(14): {self.atr_value:.5f}
"""
        
        # Add Reasoning Engine content if present
        if self.market_narrative:
            output += f"\n🧠 Razonamiento del Mercado:\n"
            for item in self.market_narrative:
                output += f"   - {item}\n"
        
        if self.strengths:
            output += f"\n💪 Fortalezas:\n"
            for item in self.strengths:
                output += f"   - {item}\n"
                
        if self.warnings:
            output += f"\n⚠️ Advertencias:\n"
            for item in self.warnings:
                output += f"   - {item}\n"

        if self.exposure_warning:
            output += f"\n⚠️ AVISO DE EXPOSICIÓN:\n   {self.exposure_warning}\n"
            
        output += f"\n{'='*50}\n"
        output += f"⚠️  ADVERTENCIA: Esta señal es solo informativa. El usuario debe ejecutar\n"
        output += f"    la orden manualmente y asume toda responsabilidad por sus operaciones.\n"
        
        return output
        return output
    
    def _format_confirmations(self) -> str:
        """Format indicator confirmations as bullet list."""
        if not self.indicator_confirmations:
            return "   - Ninguna"
        
        return "\n   ".join(f"- {conf}" for conf in self.indicator_confirmations)

    def _format_tp_targets(self) -> str:
        """Format multi-TP targets for display."""
        if not self.tp_targets:
            return f"   - TP Unico: {self.take_profit:.5f}"
        
        lines = []
        for name, data in self.tp_targets.items():
            prob = data.get('prob', 0)
            price = data.get('price', 0)
            lines.append(f"   - {name}: {price:.5f} (Probabilidad: {prob:.0%})")
        return "\n".join(lines)


class SignalGenerator:
    """Generate trading signals with complete information."""
    
    def __init__(self, capital: float = None):
        """
        Initialize signal generator.
        
        Args:
            capital: Trading capital
        """
        self.risk_calculator = RiskCalculator(capital)
        self.validity_hours = config.get_trading_config("signal.validity_hours")
        self.confidence_levels = config.get_trading_config("signal.confidence_levels")

    def update_capital(self, capital: float) -> None:
        """Update capital for risk calculations."""
        self.risk_calculator.set_capital(capital)

    def update_risk_percent(self, percent: float) -> None:
        """Update risk percentage for risk calculations."""
        self.risk_calculator.set_risk_percent(percent)
    
    def generate_signal(
        self,
        pair: str,
        direction: str,
        entry_price: float,
        atr: float,
        probability_components: ProbabilityComponents,
        trend_summary: Dict,
        indicators: Dict,
        confirmations: list,
        mc_prob: float = 0.0,
        override_timestamp: datetime = None,
        exposure_warning: str = None,
        market_narrative: list = None,
        strengths: list = None,
        warnings: list = None,
        symbol_info: object = None
    ) -> TradingSignal:
        """
        Generate complete trading signal.
        """
        logger.progress(f"Generating {direction.upper()} signal for {pair}")
        
        # Determine Order Type (MARKET vs LIMIT vs STOP)
        current_price = indicators.get('current_price', entry_price)
        order_type = self._determine_order_type(direction, entry_price, current_price, atr)
        
        # Calculate risk parameters (TP2 is the target used for R/R validation)
        risk_params = self.risk_calculator.calculate_full_risk_params(
            entry_price=entry_price,
            direction=direction.lower(),
            atr=atr,
            pair=pair,
            symbol_info=symbol_info
        )
        
        # Multi-TP Targets calculation
        tp_targets = self._calculate_tp_targets(entry_price, risk_params.stop_loss, direction, mc_prob)
        
        # Determine confidence level
        probability = probability_components.total_probability
        confidence_level = self._get_confidence_level(probability)
        
        # Calculate validity
        timestamp = override_timestamp or datetime.now()
        valid_until = timestamp + timedelta(hours=self.validity_hours)
        
        # Build justifications
        trend_analysis = self._build_trend_analysis(trend_summary)
        entry_reason = self._build_entry_reason(direction, indicators, trend_summary)
        risk_justification = self._build_risk_justification(risk_params, atr)
        
        # Create signal
        signal = TradingSignal(
            pair=pair,
            direction=direction.upper(),
            timestamp=timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            entry_price=entry_price,
            stop_loss=risk_params.stop_loss,
            take_profit=risk_params.take_profit,
            order_type=order_type,
            tp_targets=tp_targets,
            risk_pips=risk_params.risk_pips,
            reward_pips=risk_params.reward_pips,
            risk_reward_ratio=risk_params.risk_reward_ratio,
            position_size=risk_params.position_size,
            risk_amount=risk_params.risk_amount,
            probability=probability,
            monte_carlo_prob=mc_prob,
            confidence_level=confidence_level,
            valid_until=valid_until.strftime("%Y-%m-%d %H:%M:%S"),
            validity_hours=self.validity_hours,
            trend_analysis=trend_analysis,
            entry_reason=entry_reason,
            indicator_confirmations=confirmations,
            risk_justification=risk_justification,
            current_price=current_price,
            atr_value=atr,
            exposure_warning=exposure_warning,
            market_narrative=market_narrative,
            strengths=strengths,
            warnings=warnings
        )
        
        logger.success(f"Signal generated: [{order_type}] {direction.upper()} {pair} @ {entry_price:.5f}")
        logger.log_operation("signal_generated", signal.to_dict())
        
        return signal

    def _determine_order_type(self, direction: str, entry: float, current: float, atr: float) -> str:
        """Determine if it should be MARKET, LIMIT or STOP order."""
        # If very close to current price (less than 0.2 ATH), it's MARKET
        diff = abs(entry - current)
        if diff < (atr * 0.2):
            return "MARKET"
        
        if direction.lower() == "buy":
            return "LIMIT" if entry < current else "STOP"
        else: # sell
            return "LIMIT" if entry > current else "STOP"

    def _calculate_tp_targets(self, entry: float, sl: float, direction: str, base_prob: float) -> Dict:
        """Calculate TP1, TP2, TP3 targets with hit probabilities."""
        risk = abs(entry - sl)
        dir_mult = 1 if direction.lower() == "buy" else -1
        
        targets = {
            "TP1 (Seguridad)": {
                "price": round(entry + (risk * 1.0) * dir_mult, 5), # 1:1
                "prob": min(0.95, base_prob * 1.5) # Estimated boost for TP1
            },
            "TP2 (Objetivo)": {
                "price": round(entry + (risk * 2.0) * dir_mult, 5), # 2:1
                "prob": base_prob
            },
            "TP3 (Extensión)": {
                "price": round(entry + (risk * 3.5) * dir_mult, 5), # 3.5:1
                "prob": base_prob * 0.6 # Lower probability for extension
            }
        }
        return targets
    
    def _get_confidence_level(self, probability: float) -> str:
        """Determine confidence level from probability."""
        if probability >= self.confidence_levels['high']:
            return "ALTA"
        elif probability >= self.confidence_levels['medium']:
            return "MEDIA"
        else:
            return "BAJA"
    
    def _build_trend_analysis(self, trend_summary: Dict) -> str:
        """Build trend analysis text."""
        primary_trend = trend_summary.get('primary_trend')
        alignment_score = trend_summary.get('alignment_score', 0)
        
        if not primary_trend:
            return "Tendencia no disponible"
        
        direction = primary_trend.direction.upper()
        strength = primary_trend.strength
        
        tf_name = primary_trend.timeframe
        interval = config.timeframes.get(tf_name, tf_name)
        
        return (
            f"Tendencia {interval} {direction} con fuerza ADX={strength:.1f}. "
            f"Alineación multi-timeframe: {alignment_score:.0%}. "
            f"EMAs {'alineadas' if primary_trend.ema_alignment else 'no alineadas'}."
        )
    
    def _build_entry_reason(
        self,
        direction: str,
        indicators: Dict,
        trend_summary: Dict
    ) -> str:
        """Dynamic Entry Reason based on Market Regime."""
        regime = trend_summary.get('regime', 'unknown')
        adx = indicators.get('adx', 0)
        rsi = indicators.get('rsi', 50)
        
        # Build a narrative based on actual metrics
        parts = []
        if direction.lower() == "buy":
            if adx > 25: parts.append(f"Impulso alcista detectado (ADX={adx:.1f})")
            if rsi < 40: parts.append("Oversold/Dip en tendencia mayor")
            if indicators.get('macd', 0) > 0: parts.append("Momentum MACD alcista confirmando")
        else:
            if adx > 25: parts.append(f"Impulso bajista detectado (ADX={adx:.1f})")
            if rsi > 60: parts.append("Overbought/Rebote en resistencia")
            if indicators.get('macd', 0) < 0: parts.append("Momentum MACD bajista confirmando")
            
        if not parts:
            parts.append(f"Confluencia técnica en {direction.upper()}")
            
        return ". ".join(parts) + "."
    
    def _build_risk_justification(
        self,
        risk_params: RiskParameters,
        atr: float
    ) -> str:
        """Build risk management justification."""
        return (
            f"Stop Loss calculado con ATR×{self.risk_calculator.atr_multiplier} = {atr * self.risk_calculator.atr_multiplier:.5f}. "
            f"Take Profit con ratio 1:{risk_params.risk_reward_ratio:.1f} para maximizar rentabilidad. "
            f"Riesgo limitado al {self.risk_calculator.max_risk_percent}% del capital."
        )
