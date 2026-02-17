"""
Decision tree logic for signal validation.
"""
from dataclasses import dataclass
from typing import Any, Dict, Tuple, Optional
from ..ml.stop_hunt_model import StopHuntModel

from ..utils.config import config
from ..utils.logger import logger


@dataclass
class DecisionResult:
    """Result of decision tree evaluation."""
    passed: bool
    step_reached: int
    reason: str
    details: Dict


class DecisionTree:
    """
    Decision tree for signal validation.
    
    Steps:
    0. Is H1/H4 aligned with D1 trend? (The "Big Picture" filter)
    1. Is H4 trend clear? (EMA alignment + ADX > 25)
    2. Is H1 signal aligned with H4 trend?
    3. Is RSI in favorable zone? (30-70 range)
    4. Is price near support/resistance?
    5. Is probability ≥ 65%?
    """
    
    def __init__(self):
        """Initialize decision tree with configuration."""
        self.adx_threshold = config.get_trading_config("indicators.adx_threshold")
        self.prob_threshold = config.get_trading_config("probability.min_threshold")
        self.rsi_overbought = config.get_trading_config("indicators.rsi_overbought")
        self.rsi_oversold = config.get_trading_config("indicators.rsi_oversold")
        self.ml_model = StopHuntModel()
    
    def evaluate(
        self,
        trend_data: Dict,
        indicators_h1: Dict,
        indicators_h4: Dict,
        sr_levels: Dict,
        probability: float,
        config_override: Dict[str, Any] = None
    ) -> DecisionResult:
        """
        Evaluate all decision tree steps.
        """
        # Determine local thresholds
        local_adx = self.adx_threshold
        local_prob = self.prob_threshold
        local_rsi_ob = self.rsi_overbought
        local_rsi_os = self.rsi_oversold
        local_max_dist = config.get_trading_config("indicators.sr_max_distance_pips")
        
        if config_override:
            local_adx = config_override.get("indicators", {}).get("adx_threshold", local_adx)
            local_prob = config_override.get("probability", {}).get("min_threshold", local_prob)
            local_rsi_ob = config_override.get("indicators", {}).get("rsi_overbought", local_rsi_ob)
            local_rsi_os = config_override.get("indicators", {}).get("rsi_oversold", local_rsi_os)
            local_max_dist = config_override.get("indicators", {}).get("sr_max_distance_pips", local_max_dist)

        logger.progress("Evaluating decision tree")
        
        # Step 0: D1 trend alignment (Big Picture)
        ignore_d1 = config_override.get("signal", {}).get("ignore_d1_alignment", False) if config_override else False
        
        if ignore_d1:
            logger.info("Step 0: D1 Alignment ignored (Overridden by profile)")
            step0_result, step0_details = True, {'overridden': True}
        else:
            step0_result, step0_details = self._step0_d1_alignment(trend_data)
            
        if not step0_result:
            return DecisionResult(
                passed=False,
                step_reached=0,
                reason="Not aligned with D1 trend (Big Picture)",
                details=step0_details
            )

        # Step 1: H4 trend clear?
        step1_result, step1_details = self._step1_h4_trend_clear(
            trend_data, indicators_h4, local_adx
        )
        
        if not step1_result:
            return DecisionResult(
                passed=False,
                step_reached=1,
                reason="H4 trend not clear enough",
                details=step1_details
            )
        
        # Step 2: H1 aligned with H4?
        step2_result, step2_details = self._step2_h1_aligned(
            trend_data, indicators_h1
        )
        
        if not step2_result:
            return DecisionResult(
                passed=False,
                step_reached=2,
                reason="H1 signal not aligned with H4 trend",
                details=step2_details
            )
        
        # Step 3: RSI in favorable zone?
        step3_result, step3_details = self._step3_rsi_favorable(
            indicators_h1, trend_data, local_rsi_os, local_rsi_ob
        )
        
        if not step3_result:
            return DecisionResult(
                passed=False,
                step_reached=3,
                reason="RSI not in favorable zone",
                details=step3_details
            )
        
        # Step 4: Near support/resistance?
        step4_result, step4_details = self._step4_near_sr(
            indicators_h1, sr_levels, local_max_dist
        )
        
        if not step4_result:
            return DecisionResult(
                passed=False,
                step_reached=4,
                reason="Price not near key support/resistance level",
                details=step4_details
            )
        
        # Step 5: Probability threshold?
        step5_result, step5_details = self._step5_probability(probability, local_prob)
        
        if not step5_result:
            return DecisionResult(
                passed=False,
                step_reached=5,
                reason=f"Probability {probability:.1%} below threshold {local_prob:.1%}",
                details=step5_details
            )
            
        # Step 6: Anti-Stop Hunt ML Filter
        step6_result, step6_details = self._step6_ml_stop_hunt_filter(indicators_h1, config_override=config_override)
        
        if not step6_result:
            return DecisionResult(
                passed=False,
                step_reached=6,
                reason="High risk of Stop Hunt detected by ML",
                details=step6_details
            )
        
        # All steps passed!
        logger.success("✅ All decision tree steps passed")
        
        return DecisionResult(
            passed=True,
            step_reached=6,
            reason="All criteria met",
            details={
                'step1': step1_details,
                'step2': step2_details,
                'step3': step3_details,
                'step4': step4_details,
                'step5': step5_details,
                'step6': step6_details
            }
        )

    def evaluate_soft(
        self,
        trend_data: Dict,
        indicators_h1: Dict,
        indicators_h4: Dict,
        sr_levels: Dict,
        probability: float,
        config_override: Dict[str, Any] = None
    ) -> DecisionResult:
        """
        Refined Evaluation (Phase 3): Weighted scoring instead of strict gating.
        Allows for 'Prudencia Adaptable'.
        """
        # Determine local thresholds
        local_adx = self.adx_threshold
        local_prob = self.prob_threshold
        local_rsi_ob = self.rsi_overbought
        local_rsi_os = self.rsi_oversold
        local_max_dist = config.get_trading_config("indicators.sr_max_distance_pips")
        
        if config_override:
            local_adx = config_override.get("indicators", {}).get("adx_threshold", local_adx)
            local_prob = config_override.get("probability", {}).get("min_threshold", local_prob)
            local_rsi_ob = config_override.get("indicators", {}).get("rsi_overbought", local_rsi_ob)
            local_rsi_os = config_override.get("indicators", {}).get("rsi_oversold", local_rsi_os)
            local_max_dist = config_override.get("indicators", {}).get("sr_max_distance_pips", local_max_dist)

        logger.info("Evaluating decision tree (SOFT MODE)")
        
        # Determine Market Regime
        hurst = indicators_h1.get('hurst', 0.5)
        is_trending = hurst > 0.55
        is_mean_reverting = hurst < 0.45
        
        steps = []
        
        # Step 0: D1 Alignment (Weight: 1)
        res0, det0 = self._step0_d1_alignment(trend_data)
        steps.append({'val': res0, 'weight': 1.0, 'name': 'D1 Alignment'})
        
        # Step 1: H4 Trend Clear (Weight: 2) -> Critical for trend following
        res1, det1 = self._step1_h4_trend_clear(trend_data, indicators_h4, local_adx)
        steps.append({'val': res1, 'weight': 2.0 if is_trending else 1.0, 'name': 'H4 Trend Clear'})
        
        # Step 2: H1 Aligned with H4 (Weight: 1.5)
        res2, det2 = self._step2_h1_aligned(trend_data, indicators_h1)
        steps.append({'val': res2, 'weight': 1.5 if is_trending else 0.5, 'name': 'H1 Alignment'})
        
        # Step 3: RSI Favorable (Weight: 1.5) -> Critical for mean reversion
        res3, det3 = self._step3_rsi_favorable(indicators_h1, trend_data, local_rsi_os, local_rsi_ob)
        steps.append({'val': res3, 'weight': 2.0 if is_mean_reverting else 1.0, 'name': 'RSI Favorable'})
        
        # Step 4: Near S/R (Weight: 1.5)
        res4, det4 = self._step4_near_sr(indicators_h1, sr_levels, local_max_dist)
        steps.append({'val': res4, 'weight': 1.5, 'name': 'Near S/R'})
        
        # Step 5: Probability (Weight: 2)
        res5, det5 = self._step5_probability(probability, local_prob)
        steps.append({'val': res5, 'weight': 2.0, 'name': 'Min Probability'})
        
        # Step 6: ML Stop Hunt (Weight: 2) -> HIGH IMPORTANCE
        res6, det6 = self._step6_ml_stop_hunt_filter(indicators_h1, config_override=config_override)
        steps.append({'val': res6, 'weight': 2.5, 'name': 'ML Stop Hunt'})

        # Calculate weighted score
        total_weight = sum(s['weight'] for s in steps)
        earned_weight = sum(s['weight'] for s in steps if s['val'])
        score = earned_weight / total_weight
        
        # Pass threshold (Phase 3: 0.60 baseline, configurable for v8)
        pass_threshold = 0.60
        if config_override:
            pass_threshold = config_override.get("probability", {}).get("soft_decision_threshold", pass_threshold)
            
        passed = score >= pass_threshold
        
        details = {
            'score': score,
            'threshold': pass_threshold,
            'hurst': hurst,
            'trending': is_trending,
            'mean_reverting': is_mean_reverting,
            'steps': steps
        }
        
        if passed:
            logger.success(f"✅ Soft Decision Passed (Score: {score:.2%})")
        else:
            logger.warning(f"❌ Soft Decision Failed (Score: {score:.2%})")
            
        return DecisionResult(
            passed=passed,
            step_reached=len(steps),
            reason="Weighted confirmation" if passed else f"Insufficient weight ({score:.2%})",
            details=details
        )

    def _step6_ml_stop_hunt_filter(self, indicators: Dict, config_override: Optional[Dict] = None) -> Tuple[bool, Dict]:
        """Step 6: AI-driven stop hunt detection."""
        if not self.ml_model.is_trained:
            return True, {'status': 'Model not trained, skipping filter'}

        # Built-in features from indicators
        features = {
            'wick_ratio': indicators.get('wick_ratio', 1.0),
            'volatility_surge': indicators.get('atr', 0) / (indicators.get('atr_avg', 1e-6)),
            'successive_move': indicators.get('successive_move', 0.5),
            'rsi': indicators.get('rsi', 50),
            'adx': indicators.get('adx', 0)
        }
        
        risk_score = self.ml_model.predict_risk(features)
        
        # Risk threshold (adjustable)
        risk_threshold = config.get_trading_config("ml.stop_hunt_risk_threshold")
        if config_override:
            risk_threshold = config_override.get("ml", {}).get("stop_hunt_risk_threshold", risk_threshold)
            
        passed = risk_score < risk_threshold
        
        details = {
            'risk_score': risk_score,
            'threshold': risk_threshold,
            'features': features,
            'passed': passed
        }
        
        if not passed:
            logger.debug(f"⚠️ ML Filter: Stop Hunt Risk detected! (Score: {risk_score:.2%})")
        else:
            logger.debug(f"Step 6: ML Stop Hunt Risk = {risk_score:.2%}")
            
        return passed, details
    
    def _step0_d1_alignment(self, trend_data: Dict) -> Tuple[bool, Dict]:
        """Step 0: Check alignment with daily trend."""
        d1_trend = trend_data.get('timeframes', {}).get('long')
        h4_trend = trend_data.get('timeframes', {}).get('medium')
        
        if not d1_trend or not h4_trend:
            return False, {'error': 'Missing trend data'}
            
        # Si H4 tiene tendencia MUY fuerte, permitimos flexibilidad con D1
        if h4_trend and h4_trend.strength > 35:
            aligned = True
            logger.info(f"Step 0: Super Trend H4 (ADX > 35) overrides D1 Alignment")
        elif d1_trend.direction == 'neutral':
            aligned = True
        else:
            aligned = (d1_trend.direction == h4_trend.direction)
        
        details = {
            'd1_direction': d1_trend.direction,
            'h4_direction': h4_trend.direction,
            'aligned': aligned
        }
        
        logger.debug(f"Step 0: D1 Alignment = {aligned}")
        return aligned, details

    def _step1_h4_trend_clear(
        self,
        trend_data: Dict,
        indicators_h4: Dict,
        adx_threshold: float
    ) -> Tuple[bool, Dict]:
        """Step 1: Check if H4 trend is clear."""
        # Get H4 trend info
        h4_trend = trend_data.get('timeframes', {}).get('medium')
        
        if not h4_trend:
            return False, {'error': 'No H4 trend data'}
        
        # Check EMA alignment
        ema_aligned = h4_trend.ema_alignment
        
        # Check ADX
        adx = indicators_h4.get('adx', 0)
        adx_strong = adx >= adx_threshold
        
        # Both must be true
        passed = ema_aligned and adx_strong
        
        details = {
            'direction': h4_trend.direction,
            'ema_aligned': ema_aligned,
            'adx': adx,
            'adx_threshold': adx_threshold,
            'adx_strong': adx_strong
        }
        
        logger.debug(f"Step 1: H4 trend clear = {passed}")
        return passed, details
    
    def _step2_h1_aligned(
        self,
        trend_data: Dict,
        indicators_h1: Dict
    ) -> Tuple[bool, Dict]:
        """Step 2: Check if H1 signal aligned with H4 trend."""
        # Get trends
        h4_trend = trend_data.get('timeframes', {}).get('medium')
        h1_trend = trend_data.get('timeframes', {}).get('short')
        
        if not h4_trend or not h1_trend:
            return False, {'error': 'Missing trend data'}
        
        # Check if directions match
        aligned = h4_trend.direction == h1_trend.direction
        
        # Also check if H1 EMAs support the direction
        ema_12 = indicators_h1.get('ema_12', 0)
        ema_26 = indicators_h1.get('ema_26', 0)
        
        if h4_trend.direction == 'bullish':
            ema_support = ema_12 > ema_26
        elif h4_trend.direction == 'bearish':
            ema_support = ema_12 < ema_26
        else:
            ema_support = False
        
        passed = aligned and ema_support
        
        details = {
            'h4_direction': h4_trend.direction,
            'h1_direction': h1_trend.direction,
            'aligned': aligned,
            'ema_support': ema_support
        }
        
        logger.debug(f"Step 2: H1 aligned = {passed}")
        return passed, details
    
    def _step3_rsi_favorable(
        self,
        indicators: Dict,
        trend_data: Dict,
        rsi_oversold: float,
        rsi_overbought: float
    ) -> Tuple[bool, Dict]:
        """Step 3: Check if RSI is in favorable zone."""
        rsi = indicators.get('rsi', 50)
        consensus = trend_data.get('consensus', 'neutral')
        
        # For bullish/bearish: RSI should be in range
        if consensus in ['bullish', 'bearish']:
            favorable = rsi_oversold <= rsi <= rsi_overbought
        else:
            favorable = False
        
        details = {
            'rsi': rsi,
            'consensus': consensus,
            'favorable_range': f"{rsi_oversold}-{rsi_overbought}",
            'in_range': favorable
        }
        
        logger.debug(f"Step 3: RSI favorable = {favorable}")
        return favorable, details
    
    def _step4_near_sr(
        self,
        indicators: Dict,
        sr_levels: Dict,
        max_distance_pips: float
    ) -> Tuple[bool, Dict]:
        """Step 4: Check if price near support/resistance."""
        current_price = indicators.get('current_price', 0)
        pair = indicators.get('pair', 'EURUSD')
        
        if not current_price:
            return False, {'error': 'No current price'}
        
        # Get nearest levels
        nearest_support = sr_levels.get('nearest_support')
        nearest_resistance = sr_levels.get('nearest_resistance')
        
        # Check if near any level (dynamic distance from profile)
        pip_multiplier = 100 if "JPY" in pair.upper() else 10000
        
        near_support = False
        near_resistance = False
        
        if nearest_support:
            distance_pips = abs(current_price - nearest_support) * pip_multiplier
            near_support = distance_pips <= max_distance_pips
        
        if nearest_resistance:
            distance_pips = abs(current_price - nearest_resistance) * pip_multiplier
            near_resistance = distance_pips <= max_distance_pips
        
        passed = near_support or near_resistance
        
        details = {
            'current_price': current_price,
            'nearest_support': nearest_support,
            'nearest_resistance': nearest_resistance,
            'near_support': near_support,
            'near_resistance': near_resistance,
            'max_distance_pips': max_distance_pips,
            'pip_multiplier': pip_multiplier
        }
        
        logger.debug(f"Step 4: Near S/R = {passed} (pip_mult: {pip_multiplier})")
        return passed, details
    
    def _step5_probability(self, probability: float, prob_threshold: float) -> Tuple[bool, Dict]:
        """Step 5: Check if probability meets threshold."""
        passed = probability >= prob_threshold
        
        details = {
            'probability': probability,
            'threshold': prob_threshold,
            'meets_threshold': passed
        }
        
        logger.debug(f"Step 5: Probability {probability:.1%} >= {prob_threshold:.1%} = {passed}")
        return passed, details
