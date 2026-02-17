"""
Main trading agent orchestrator that coordinates all components.
"""
from typing import Optional, Dict
from datetime import datetime
import pandas as pd

from .api.api_manager import api_manager
from .analysis.trend_analyzer import TrendAnalyzer
from .analysis.indicators import IndicatorAnalyzer
from .analysis.pattern_recognition import PatternRecognizer
from .probability.kalman_filter import KalmanProbabilityFilter
from .probability.decision_tree import DecisionTree
from .probability.monte_carlo import MonteCarloValidator
from .signals.signal_generator import SignalGenerator, TradingSignal
from .analysis.reasoning_engine import ReasoningEngine
from .tracking.trade_tracker import TradeTracker
from .utils.config import config
from .utils.logger import logger


class TradingAgent:
    """Main trading agent that orchestrates analysis and signal generation."""
    
    def __init__(self, capital: float = None):
        """
        Initialize trading agent.
        
        Args:
            capital: Trading capital (uses config default if not provided)
        """
        self.capital = capital or config.get_trading_config("risk_management.default_capital")
        
        # Initialize components
        self.probability_filter = KalmanProbabilityFilter()
        self.decision_tree = DecisionTree()
        self.monte_carlo = MonteCarloValidator()
        self.signal_generator = SignalGenerator(self.capital)
        self.trade_tracker = TradeTracker()
        self.reasoning_engine = ReasoningEngine()
        
        logger.success(f"Trading Agent initialized with capital: ${self.capital:,.2f}")

    @property
    def timeframes(self):
        """Dynamic access to timeframes from config profile."""
        return config.timeframes

    def update_capital(self, capital: float) -> None:
        """Update capital for analysis."""
        self.capital = capital
        self.signal_generator.update_capital(capital)

    def update_risk_percent(self, percent: float) -> None:
        """Update risk percentage for analysis."""
        self.signal_generator.update_risk_percent(percent)

    def has_exposure_on_base(self, pair: str) -> bool:
        """
        Check if we already have an open trade involving the base currency of the pair.
        Used to prevent over-exposure to correlated movements (e.g., USD strength).
        """
        # Simple implementation: check if the first 3 chars or last 3 chars match
        # in any currently open trade.
        base = pair[:3]
        quote = pair[3:]
        open_trades = self.trade_tracker.get_open_trades()
        
        for trade in open_trades:
            t_pair = trade['pair']
            if base in t_pair or quote in t_pair:
                return True
        return False
    
    def analyze_pair(
        self,
        pair: str,
        manual_data: Dict[str, pd.DataFrame] = None,
        override_timestamp: datetime = None,
        config_override: Dict[str, Any] = None
    ) -> Optional[TradingSignal]:
        """
        Perform complete analysis of a currency pair.
        
        Args:
            pair: Currency pair to analyze (e.g., "EURUSD")
            manual_data: Optional dictionary mapping timeframe intervals to dataframes
            override_timestamp: Optional historical timestamp
        
        Returns:
            TradingSignal if conditions met, None otherwise
        """
        try:
            # Use provided config or global config
            ctx_config = config_override if config_override else config.trading
            
            # Helper to get config values from local context
            def get_cfg(key: str) -> Any:
                keys = key.split('.')
                v = ctx_config
                for k in keys:
                    if isinstance(v, dict) and k in v:
                        v = v[k]
                    else:
                        # Fallback to global if missing in override
                        return config.get_trading_config(key)
                return v
            
            # Profile name for logging
            profile_name = get_cfg("name") if config_override else config.get_trading_config("active_profile")
            logger.info(f"\n{'='*60}")
            logger.info(f"🔍 ANALIZANDO {pair} | PERFIL: {profile_name}")
            logger.info(f"{'='*60}\n")
            
            # Robustness Check: Exposure Control
            if self.has_exposure_on_base(pair):
                logger.warning(f"⚠️  Exposición máxima alcanzada para moneda base relacionada a {pair}")
                return None
            # Step 1: Multi-timeframe trend analysis
            logger.progress("Paso 1/7: Análisis de tendencia multi-timeframe", 7, 1)
            tfs = get_cfg("timeframes")
            trend_analyzer = TrendAnalyzer(pair, timeframes=tfs, data=manual_data)
            trend_analyzer.analyze_all_timeframes()
            trend_summary = trend_analyzer.get_summary()
            
            # Step 2: Get entry timeframe data
            short_interval = self.timeframes.get('short', '15min')
            logger.progress(f"Paso 2/7: Obteniendo datos {short_interval} para señales de entrada", 7, 2)
            h1_interval = short_interval
            
            if manual_data and h1_interval in manual_data:
                h1_data = manual_data[h1_interval]
            else:
                h1_data = api_manager.get_forex_data(pair, h1_interval, outputsize="full")
                
            h1_analyzer = IndicatorAnalyzer(h1_data)
            h1_indicators = h1_analyzer.get_latest_values()
            h1_indicators['trend_direction'] = h1_analyzer.get_trend_direction()
            h1_indicators['pair'] = pair
            
            # Step 3: Pattern recognition
            logger.progress("Paso 3/7: Reconocimiento de patrones", 7, 3)
            pattern_recognizer = PatternRecognizer(pair, h1_data)
            bullish_patterns = pattern_recognizer.get_bullish_patterns()
            bearish_patterns = pattern_recognizer.get_bearish_patterns()
            
            current_price = h1_indicators['current_price']
            nearest_support = pattern_recognizer.get_nearest_support(current_price)
            nearest_resistance = pattern_recognizer.get_nearest_resistance(current_price)
            
            # Step 4: Calculate probability
            logger.progress("Paso 4/7: Calculando probabilidad", 7, 4)
            
            # Prepare volatility data
            atr_current = h1_indicators['atr']
            
            # Safely get short-term analyzer and its ATR series
            short_analyzer = trend_analyzer.analyzers.get('short')
            if short_analyzer:
                atr_series = short_analyzer.indicators['atr']
                atr_avg = atr_series.tail(50).mean()
            else:
                # Fallback if short-term data is missing
                logger.warning(f"Short-term analyzer missing for {pair}, using ATR as average fallback.")
                atr_avg = atr_current
            
            volatility_data = {
                'current_atr': atr_current,
                'avg_atr': atr_avg
            }
            
            # Prepare pattern data
            pattern_data = {
                'bullish_patterns': bullish_patterns,
                'bearish_patterns': bearish_patterns
            }
            
            # Calculate probability
            probability_components = self.probability_filter.calculate_probability(
                trend_data=trend_summary,
                indicators=h1_indicators,
                volatility_data=volatility_data,
                patterns=pattern_data
            )
            
            # Step 5: Decision tree evaluation
            logger.progress("Paso 5/7: Evaluando árbol de decisiones", 7, 5)
            
            # Get medium timeframe indicators
            h4_analyzer = trend_analyzer.analyzers.get('medium')
            h4_indicators = h4_analyzer.get_latest_values() if h4_analyzer else {}
            
            # Prepare S/R data
            sr_data = {
                'nearest_support': nearest_support,
                'nearest_resistance': nearest_resistance
            }
            
            # Custom DecisionTree invocation with Phase 3 Soft Evaluation
            decision_result = self.decision_tree.evaluate_soft(
                trend_data=trend_summary,
                indicators_h1=h1_indicators,
                indicators_h4=h4_indicators,
                sr_levels=sr_data,
                probability=probability_components.total_probability,
                config_override=ctx_config
            )
            
            # Check if decision tree passed
            if not decision_result.passed:
                logger.debug(f"❌ No hay señal clara para {pair}")
                logger.debug(f"Razón: {decision_result.reason}")
                logger.debug(f"Paso alcanzado: {decision_result.step_reached}/6")
                
                self._print_no_signal_details(decision_result, probability_components)
                return None
            
            # Determine direction from consensus
            consensus = trend_summary['consensus']
            if consensus == 'neutral':
                logger.debug(f"❌ Señal descartada por consenso neutral")
                return None
                
            direction = "buy" if consensus == "bullish" else "sell"
            
            # Predict exit levels for simulation
            # Phase 5: Decoupled ATR Multipliers
            atr_sl_mult = ctx_config.get("risk_management", {}).get("atr_multiplier_sl", get_cfg("risk_management.atr_multiplier_stop_loss"))
            if atr_sl_mult is None: atr_sl_mult = 1.5
            atr_tp_mult = ctx_config.get("risk_management", {}).get("atr_multiplier_tp", atr_sl_mult * get_cfg("risk_management.min_risk_reward_ratio"))
            if atr_tp_mult is None: atr_tp_mult = atr_sl_mult * 2.0
            
            sl_dist = atr_current * atr_sl_mult
            tp_dist = atr_current * atr_tp_mult
            
            tp_temp = current_price + tp_dist if direction == "buy" else current_price - tp_dist
            sl_temp = current_price - sl_dist if direction == "buy" else current_price + sl_dist

            # Step 6: Monte Carlo statistical validation
            logger.progress("Paso 6/7: Validación estadística Monte Carlo", 7, 6)
            
            mc_prob, mc_passed = self.monte_carlo.validate_signal(
                entry=current_price,
                tp=tp_temp,
                sl=sl_temp,
                atr=atr_current,
                direction=direction,
                trend_strength=h4_indicators.get('adx', 0)
            )

            # Phase 3 & 4: Relaxed Monte Carlo Gating
            mc_threshold = ctx_config.get("probability", {}).get("min_monte_carlo_prob", 0.35)
            if not mc_passed and mc_prob < mc_threshold: # Respect configured threshold
                logger.warning(f"❌ Señal descartada por probabilidad estadística insuficiente (MC: {mc_prob:.1%} < {mc_threshold:.1%})")
                return None
            elif not mc_passed:
                logger.info(f"⚠️ MC Prob ({mc_prob:.1%}) below threshold but allowed by Phase 3 Soft Gating")

            # Step 7: Generate signal
            logger.progress("Paso 7/7: Generando señal de trading", 7, 7)
            
            # Reasoning Engine Context (Manual Assistant)
            reasoning_context = self.reasoning_engine.generate_context(
                trend_data=trend_summary,
                indicators_h1=h1_indicators,
                indicators_h4=h4_indicators,
                probability=probability_components.total_probability,
                monte_carlo_prob=mc_prob
            )

            # Determine entry price (current price or near S/R)
            if direction == "buy" and nearest_support:
                entry_price = nearest_support
            elif direction == "sell" and nearest_resistance:
                entry_price = nearest_resistance
            else:
                entry_price = current_price
            
            # Build confirmations list
            confirmations = self._build_confirmations(
                h1_indicators,
                h4_indicators,
                trend_summary,
                bullish_patterns if direction == "buy" else bearish_patterns
            )
            
            # Check for exposure
            exposure_warning = None
            if self.trade_tracker.has_open_trade(pair):
                exposure_warning = f"Ya tienes una operación abierta en {pair}. Abrir otra podría causar sobre-apalancamiento (Rule of Thumb: Máx 1 trade por par)."

            # Generate signal
            signal = self.signal_generator.generate_signal(
                pair=pair,
                direction=direction,
                entry_price=entry_price,
                atr=atr_current,
                probability_components=probability_components,
                trend_summary=trend_summary,
                indicators=h1_indicators,
                confirmations=confirmations,
                mc_prob=mc_prob,
                override_timestamp=override_timestamp,
                exposure_warning=exposure_warning,
                market_narrative=reasoning_context['narrative'],
                strengths=reasoning_context['strengths'],
                warnings=reasoning_context['warnings']
            )
            
            logger.success(f"\n✅ SEÑAL GENERADA PARA {pair}\n")
            
            return signal
        
        except Exception as e:
            logger.error(f"Error analyzing {pair}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    def analyze_scalp_pair(
        self,
        pair: str,
        manual_data: Dict[str, pd.DataFrame] = None,
        override_timestamp: datetime = None,
        config_override: Dict[str, Any] = None
    ) -> Optional[TradingSignal]:
        """
        Special version of analyze_pair that iterates through RR levels (1.1 to 1.5)
        to find the "Sweet Spot" with the highest Monte Carlo probability.
        Designed for 'Modo Dopamina'.
        """
        best_signal = None
        best_mc_prob = 0
        
        # Use provided override or default prop_scalper
        base_cfg = config_override if config_override else config.get_profile_config('prop_scalper')
        rr_steps = [1.1, 1.2, 1.3, 1.4, 1.5]
        
        logger.info(f"🚀 INICIANDO BÚSQUEDA DOPAMINA (Scalping de Alta Probabilidad) para {pair}")
        
        for rr in rr_steps:
            # Shift the RR in the local config copy
            local_cfg = base_cfg.copy()
            local_cfg['risk_management'] = local_cfg.get('risk_management', {}).copy()
            local_cfg['risk_management']['min_risk_reward_ratio'] = rr
            
            logger.debug(f"🧪 Probando balance RR: {rr}...")
            
            # Use analyze_pair but with the specific RR
            signal = self.analyze_pair(
                pair, 
                manual_data=manual_data, 
                override_timestamp=override_timestamp,
                config_override=local_cfg
            )
            
            if signal:
                # We compare Monte Carlo probabilities
                # Note: signal.monte_carlo_prob is what we want
                if signal.monte_carlo_prob > best_mc_prob:
                    best_mc_prob = signal.monte_carlo_prob
                    best_signal = signal
                    
        if best_signal:
            logger.success(f"🎯 ¡DULCE PUNTO ENCONTRADO! RR: {best_signal.risk_reward_ratio:.2f} | Prob MC: {best_signal.monte_carlo_prob:.1%}")
        else:
            logger.warning(f"❌ No se encontró ningún 'Sweet Spot' seguro para {pair} con RR >= 1.1")
            
        return best_signal
    
    def _print_no_signal_details(self, decision_result, probability_components):
        """Print details when no signal is generated."""
        logger.info("\n📊 Detalles del análisis:")
        logger.info(f"   - Probabilidad total: {probability_components.total_probability:.1%}")
        logger.info(f"   - Confianza tendencia: {probability_components.trend_confidence:.1%}")
        logger.info(f"   - Confirmación indicadores: {probability_components.indicator_confirmation:.1%}")
        logger.info(f"   - Favorabilidad volatilidad: {probability_components.volatility_favorability:.1%}")
        logger.info(f"   - Sentimiento mercado: {probability_components.market_sentiment:.1%}")
        logger.info("\n💡 Recomendación: Esperar mejores condiciones.\n")
    
    def _build_confirmations(
        self,
        h1_indicators: Dict,
        h4_indicators: Dict,
        trend_summary: Dict,
        patterns: list
    ) -> list:
        """Build list of indicator confirmations."""
        confirmations = []
        consensus = trend_summary['consensus']
        
        # EMA confirmation
        ema_12 = h1_indicators.get('ema_12', 0)
        ema_26 = h1_indicators.get('ema_26', 0)
        if consensus == 'bullish' and ema_12 > ema_26:
            confirmations.append(f"EMA12 ({ema_12:.5f}) > EMA26 ({ema_26:.5f})")
        elif consensus == 'bearish' and ema_12 < ema_26:
            confirmations.append(f"EMA12 ({ema_12:.5f}) < EMA26 ({ema_26:.5f})")
        
        # MACD confirmation
        macd = h1_indicators.get('macd', 0)
        if consensus == 'bullish' and macd > 0:
            confirmations.append(f"MACD positivo ({macd:.5f})")
        elif consensus == 'bearish' and macd < 0:
            confirmations.append(f"MACD negativo ({macd:.5f})")
        
        # RSI confirmation
        rsi = h1_indicators.get('rsi', 50)
        if 30 <= rsi <= 70:
            confirmations.append(f"RSI en zona favorable ({rsi:.1f})")
        
        # ADX confirmation
        adx = h4_indicators.get('adx', 0)
        if adx >= 25:
            confirmations.append(f"ADX fuerte en H4 ({adx:.1f})")
        
        # Pattern confirmation
        if patterns:
            confirmations.append(f"Patrón detectado: {', '.join(patterns)}")
        
        return confirmations
    
    def analyze_multiple_pairs(self, pairs: list = None) -> Dict[str, Optional[TradingSignal]]:
        """
        Analyze multiple currency pairs.
        
        Args:
            pairs: List of pairs to analyze (uses config default if not provided)
        
        Returns:
            Dictionary mapping pairs to signals (or None)
        """
        pairs = pairs or config.pairs
        
        logger.info(f"\n🔍 Analizando {len(pairs)} pares de divisas...\n")
        
        results = {}
        
        for i, pair in enumerate(pairs, 1):
            logger.info(f"\n[{i}/{len(pairs)}] Analizando {pair}...")
            signal = self.analyze_pair(pair)
            results[pair] = signal
        
        # Summary
        signals_found = sum(1 for s in results.values() if s is not None)
        logger.info(f"\n{'='*60}")
        logger.success(f"✅ Análisis completado: {signals_found} señales encontradas de {len(pairs)} pares")
        logger.info(f"{'='*60}\n")
        
        return results

    def analyze_pair_layered(
        self,
        pair: str,
        manual_data: Dict[str, pd.DataFrame] = None,
        override_timestamp: datetime = None,
        config_override: Dict[str, Any] = None,
    ) -> Optional[TradingSignal]:
        """
        Phase 4: Bottom-Up Assembly.
        1. Base Signal (Primitive)
        2. ML Pruning (The 'Podador')
        3. Regime/Prob Filter (The 'Guardián')
        """
        # Step 0: Ensure we have data
        if manual_data is None:
            return self.analyze_pair(pair, config_override=config_override)
        
        # Step 1: Layer 1 - El Primitivo (Raw Signal)
        raw_signal = self._get_primitive_signal(pair, manual_data, override_timestamp, config_override)
        if not raw_signal:
            return None
            
        logger.info(f"🟢 Layer 1 (Primitive) Passed: {raw_signal['direction']} @ {raw_signal['entry_price']}")

        # Step 2: Layer 2 - El Podador (ML Pruning)
        # We only kill high-risk (Risk > 80%), not to block Uncertain.
        indicators_h1 = self._get_indicators_from_manual(manual_data, '15min')
        features = {
            'wick_ratio': indicators_h1.get('wick_ratio', 1.0),
            'volatility_surge': indicators_h1.get('atr', 0) / (indicators_h1.get('atr_avg', 1e-6)),
            'successive_move': indicators_h1.get('successive_move', 0.5),
            'rsi': indicators_h1.get('rsi', 50),
            'adx': indicators_h1.get('adx', 0)
        }
        
        if self.decision_tree.ml_model.is_trained:
            risk_score = self.decision_tree.ml_model.predict_risk(features)
            # CRITICAL: We only prune if risk is EXTREME (>80%)
            if risk_score > 0.80:
                logger.warning(f"✂️ Layer 2 (ML Pruning): Signal KILLED. Risk={risk_score:.2%}")
                return None
            logger.info(f"🛡️ Layer 2 (ML Pruning) Passed. Risk={risk_score:.2%}")

        # Step 3: Layer 3 - El Guardián (Regime & Soft Decision)
        # Delegate to the refined analyze_pair which now uses evaluate_soft
        return self.analyze_pair(pair, manual_data, override_timestamp, config_override)

    def _get_primitive_signal(self, pair: str, data: Dict, ts: datetime, cfg: Dict) -> Optional[Dict]:
        """Layer 1: Primitive Technical Signal (Literature Templates)"""
        h1_data = data.get('15min')
        if h1_data is None or len(h1_data) < 50:
            return None
            
        analyzer = IndicatorAnalyzer(h1_data)
        inds = analyzer.get_latest_values()
        
        # Template selection (default to basic EMA cross)
        template = cfg.get("strategy_template", "basic_ema_cross")
        direction = None
        
        if template == "basic_ema_cross":
            ema_12 = inds.get('ema_12', 0)
            ema_26 = inds.get('ema_26', 0)
            rsi = inds.get('rsi', 50)
            if ema_12 > ema_26 and rsi > 45:
                direction = "buy"
            elif ema_12 < ema_26 and rsi < 55:
                direction = "sell"
                
        elif template == "lit_ema_9_15_vol":
            # EMA 9/15 Crossover + Volume Confirmation
            ema_9 = inds.get('ema_9', 0)
            ema_15 = inds.get('ema_15', 0)
            vol_ratio = inds.get('volume_ratio', 1.0)
            if ema_9 > ema_15 and vol_ratio > 1.1:
                direction = "buy"
            elif ema_9 < ema_15 and vol_ratio > 1.1:
                direction = "sell"
                
        elif template == "lit_ema_9_15_atr":
            # EMA 9/15 Crossover + ATR Volatility Filter
            # Fallback option: Robust against directional noise
            # Requires active market (Volatility > Average)
            ema_9 = inds.get('ema_9', 0)
            ema_15 = inds.get('ema_15', 0)
            atr = inds.get('atr', 0)
            
            # Calculate ATR MA (20 periods) manually or get from indicators
            # IndicatorAnalyzer computes 'atr_avg' (20 periods)
            atr_avg = inds.get('atr_avg', 0)
            
            # Filter: ATR must be 10% higher than average (Expansion)
            is_volatile = atr > atr_avg * 1.1
            
            if ema_9 > ema_15 and is_volatile:
                direction = "buy"
            elif ema_9 < ema_15 and is_volatile:
                direction = "sell"
                
        elif template == "lit_multi_ma":
            # Multi-MA Trend (Price > 9 > 15 > 50 > 200)
            price = inds.get('current_price', 0)
            e9, e15, e50, e200 = inds.get('ema_9', 0), inds.get('ema_15', 0), inds.get('ema_50', 0), inds.get('ema_200', 0)
            if price > e9 > e15 > e50 > e200:
                direction = "buy"
            elif price < e9 < e15 < e50 < e200:
                direction = "sell"
                
        elif template == "lit_confluence":
            # EMA + RSI + MACD alignment
            e12, e26 = inds.get('ema_12', 0), inds.get('ema_26', 0)
            rsi = inds.get('rsi', 50)
            hist = inds.get('macd_histogram', 0)
            if e12 > e26 and rsi > 50 and hist > 0:
                direction = "buy"
            elif e12 < e26 and rsi < 50 and hist < 0:
                direction = "sell"
                
        elif template == "dopamine_m5_scalper":
            # M5 Scalper: High-frequency, low-precision for daily dopamine
            # Uses 5min data instead of 15min
            m5_data = data.get('5min')
            if m5_data is None or len(m5_data) < 50:
                return None
            
            # Calculate M5 indicators
            ema5 = m5_data['close'].ewm(span=5).mean()
            ema13 = m5_data['close'].ewm(span=13).mean()
            
            # RSI for M5
            delta = m5_data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi_m5 = 100 - (100 / (1 + rs))
            
            # ATR for volatility check
            import pandas as pd
            import numpy as np
            high_low = m5_data['high'] - m5_data['low']
            high_close = abs(m5_data['high'] - m5_data['close'].shift())
            low_close = abs(m5_data['low'] - m5_data['close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            atr_m5 = true_range.rolling(14).mean()
            atr_ma = atr_m5.rolling(20).mean()
            
            # NO SESSION FILTER - Allow 24/7 signals for maximum frequency
            
            # RELAXED BUY: EMA5 > EMA13 (trending up), RSI 35-65, ATR > 0.6× average
            if (ema5.iloc[-1] > ema13.iloc[-1] and
                ema5.iloc[-2] <= ema13.iloc[-1] * 1.001 and  # Near or actual crossover
                35 <= rsi_m5.iloc[-1] <= 65 and
                atr_m5.iloc[-1] > atr_ma.iloc[-1] * 0.6):
                direction = "buy"
            
            # RELAXED SELL: EMA5 < EMA13 (trending down), RSI 35-65, ATR > 0.6× average
            elif (ema5.iloc[-1] < ema13.iloc[-1] and
                  ema5.iloc[-2] >= ema13.iloc[-1] * 0.999 and  # Near or actual crossover
                  35 <= rsi_m5.iloc[-1] <= 65 and
                  atr_m5.iloc[-1] > atr_ma.iloc[-1] * 0.6):
                direction = "sell"
            
        if not direction:
            return None
            
        # Return simple dict for internal pass
        return {
            'direction': direction,
            'entry_price': inds.get('current_price', 0)
        }

    def _get_indicators_from_manual(self, data: Dict, tf: str) -> Dict:
        """Helper to get indicators for a specific timeframe in tiered mode."""
        df = data.get(tf)
        if df is None: return {}
        return IndicatorAnalyzer(df).get_latest_values()
