"""
Simplified Kalman filter for probability estimation.
"""
import numpy as np
from typing import Dict
from dataclasses import dataclass

from ..utils.config import config
from ..utils.logger import logger


@dataclass
class ProbabilityComponents:
    """Components of probability calculation."""
    trend_confidence: float  # 0-1
    indicator_confirmation: float  # 0-1
    volatility_favorability: float  # 0-1
    market_sentiment: float  # 0-1
    total_probability: float  # 0-1
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'trend_confidence': self.trend_confidence,
            'indicator_confirmation': self.indicator_confirmation,
            'volatility_favorability': self.volatility_favorability,
            'market_sentiment': self.market_sentiment,
            'total_probability': self.total_probability
        }


class KalmanProbabilityFilter:
    """
    Simplified Kalman filter for trading signal probability.
    
    Formula:
    P(success) = (Trend_Confidence × 0.4) + 
                 (Indicator_Confirmation × 0.3) + 
                 (Volatility_Favorability × 0.2) + 
                 (Market_Sentiment × 0.1)
    """
    
    def __init__(self):
        """Initialize with configuration weights."""
        self.weights = config.get_trading_config("probability.weights")
        self.analyzed_indicators = {}
        logger.debug(f"Kalman filter initialized with weights: {self.weights}")
    
    def calculate_probability(
        self,
        trend_data: Dict,
        indicators: Dict,
        volatility_data: Dict,
        patterns: Dict
    ) -> ProbabilityComponents:
        """
        Calculate overall probability of success.
        
        Args:
            trend_data: Multi-timeframe trend analysis
            indicators: Latest indicator values
            volatility_data: Volatility metrics
            patterns: Detected patterns
        
        Returns:
            ProbabilityComponents with breakdown
        """
        self.analyzed_indicators = indicators
        logger.progress("Calculating probability using Kalman filter")
        
        # Calculate each component
        trend_conf = self._calculate_trend_confidence(trend_data)
        indicator_conf = self._calculate_indicator_confirmation(indicators, trend_data)
        volatility_fav = self._calculate_volatility_favorability(volatility_data)
        sentiment = self._calculate_market_sentiment(patterns, indicators)
        
        # Weighted sum
        total_prob = (
            trend_conf * self.weights['trend_confidence'] +
            indicator_conf * self.weights['indicator_confirmation'] +
            volatility_fav * self.weights['volatility_favorability'] +
            sentiment * self.weights['market_sentiment']
        )
        
        # Ensure bounds
        total_prob = max(0.0, min(1.0, total_prob))
        
        logger.success(f"Probability calculated: {total_prob:.1%}")
        
        return ProbabilityComponents(
            trend_confidence=trend_conf,
            indicator_confirmation=indicator_conf,
            volatility_favorability=volatility_fav,
            market_sentiment=sentiment,
            total_probability=total_prob
        )
    
    def _calculate_trend_confidence(self, trend_data: Dict) -> float:
        """
        Calculate trend confidence from multi-timeframe alignment.
        
        Args:
            trend_data: Trend analysis data
        
        Returns:
            Confidence score (0-1)
        """
        alignment_score = trend_data.get('alignment_score', 0.0)
        primary_trend = trend_data.get('primary_trend')
        
        if not primary_trend:
            return 0.0
        
        # Base score from alignment
        score = alignment_score * 0.6
        
        # Add primary trend confidence
        score += primary_trend.confidence * 0.4
        
        logger.debug(f"Trend confidence: {score:.2f}")
        return score
    
    def _calculate_indicator_confirmation(
        self,
        indicators: Dict,
        trend_data: Dict
    ) -> float:
        """
        Calculate indicator confirmation score.
        Requires minimum 3 out of 5 indicators to confirm.
        
        Args:
            indicators: Latest indicator values
            trend_data: Trend analysis
        
        Returns:
            Confirmation score (0-1)
        """
        consensus = trend_data.get('consensus', 'neutral')
        
        if consensus == 'neutral':
            return 0.0
        
        confirmations = 0
        total_indicators = 5
        
        # 1. EMA alignment
        ema_12 = indicators.get('ema_12', 0)
        ema_26 = indicators.get('ema_26', 0)
        if consensus == 'bullish' and ema_12 > ema_26:
            confirmations += 1
        elif consensus == 'bearish' and ema_12 < ema_26:
            confirmations += 1
        
        # 2. MACD
        macd = indicators.get('macd', 0)
        if consensus == 'bullish' and macd > 0:
            confirmations += 1
        elif consensus == 'bearish' and macd < 0:
            confirmations += 1
        
        # 3. RSI (not extreme)
        rsi = indicators.get('rsi', 50)
        if consensus == 'bullish' and 40 <= rsi <= 70:
            confirmations += 1
        elif consensus == 'bearish' and 30 <= rsi <= 60:
            confirmations += 1
        
        # 4. ADX (strong trend)
        adx = indicators.get('adx', 0)
        adx_threshold = config.get_trading_config("indicators.adx_threshold")
        if adx >= adx_threshold:
            confirmations += 1
        
        # 5. MACD Histogram (momentum)
        macd_hist = indicators.get('macd_histogram', 0)
        if consensus == 'bullish' and macd_hist > 0:
            confirmations += 1
        elif consensus == 'bearish' and macd_hist < 0:
            confirmations += 1
        
        # Calculate score
        score = confirmations / total_indicators
        
        # Check minimum threshold
        min_confirmations = config.get_trading_config("probability.min_indicator_confirmations")
        if confirmations < min_confirmations:
            score *= 0.5  # Penalize if below minimum
        
        logger.debug(f"Indicator confirmation: {confirmations}/{total_indicators} = {score:.2f}")
        return score
    
    def _calculate_volatility_favorability(self, volatility_data: Dict) -> float:
        """
        Calculate volatility favorability.
        Favorable = current volatility is normal (not too high/low).
        
        Args:
            volatility_data: Volatility metrics
        
        Returns:
            Favorability score (0-1)
        """
        current_atr = volatility_data.get('current_atr', 0)
        avg_atr = volatility_data.get('avg_atr', current_atr)
        
        if avg_atr == 0:
            return 0.5  # Neutral if no data
        
        # Calculate ratio
        ratio = current_atr / avg_atr
        
        # Optimal range: 0.8 to 1.2 (normal volatility)
        if 0.8 <= ratio <= 1.2:
            score = 1.0
        elif 0.6 <= ratio < 0.8 or 1.2 < ratio <= 1.5:
            score = 0.7  # Slightly abnormal
        elif 0.4 <= ratio < 0.6 or 1.5 < ratio <= 2.0:
            score = 0.4  # Quite abnormal
        else:
            score = 0.2  # Very abnormal
        
        logger.debug(f"Volatility favorability: {score:.2f} (ratio: {ratio:.2f})")
        return score
    
    def _calculate_market_sentiment(
        self,
        patterns: Dict,
        indicators: Dict
    ) -> float:
        """
        Calculate market sentiment from patterns and price action.
        
        Args:
            patterns: Detected candlestick patterns
            indicators: Latest indicators
        
        Returns:
            Sentiment score (0-1)
        """
        score = 0.5  # Neutral baseline
        
        # Bullish patterns add to score
        bullish_patterns = patterns.get('bullish_patterns', [])
        score += len(bullish_patterns) * 0.1
        
        # Bearish patterns subtract from score
        bearish_patterns = patterns.get('bearish_patterns', [])
        score -= len(bearish_patterns) * 0.1
        
        # Bollinger Bands position
        current_price = indicators.get('current_price', 0)
        bb_upper = indicators.get('bb_upper', 0)
        bb_lower = indicators.get('bb_lower', 0)
        bb_middle = indicators.get('bb_middle', 0)
        
        if bb_upper and bb_lower and current_price:
            # Near lower band = oversold = bullish sentiment
            if current_price < bb_middle:
                distance_to_lower = abs(current_price - bb_lower)
                distance_to_middle = abs(bb_middle - bb_lower)
                if distance_to_middle > 0:
                    score += 0.2 * (1 - distance_to_lower / distance_to_middle)
            
            # Near upper band = overbought = bearish sentiment
            elif current_price > bb_middle:
                distance_to_upper = abs(bb_upper - current_price)
                distance_to_middle = abs(bb_upper - bb_middle)
                if distance_to_middle > 0:
                    score -= 0.2 * (1 - distance_to_upper / distance_to_middle)
        
        # Ensure bounds
        score = max(0.0, min(1.0, score))
        
        logger.debug(f"Market sentiment: {score:.2f}")
        return score
