"""
Multi-timeframe trend analysis and alignment detection.
"""
import pandas as pd
from typing import Dict, List
from dataclasses import dataclass

from ..api.api_manager import api_manager
from .indicators import IndicatorAnalyzer
from ..utils.config import config
from ..utils.logger import logger


@dataclass
class TrendInfo:
    """Information about trend in a specific timeframe."""
    timeframe: str
    direction: str  # "bullish", "bearish", "neutral"
    strength: float  # ADX value
    confidence: float  # 0-1 score
    ema_alignment: bool  # Are EMAs aligned with trend?


class TrendAnalyzer:
    """Analyze trends across multiple timeframes."""
    
    def __init__(self, pair: str, timeframes: Dict[str, str] = None, data: Dict[str, pd.DataFrame] = None):
        """
        Initialize trend analyzer for a currency pair.
        
        Args:
            pair: Currency pair (e.g., "EURUSD")
            timeframes: Dictionary mapping timeframe names to intervals
            data: Optional dictionary mapping timeframe intervals to dataframes
        """
        self.pair = pair
        self.timeframes = timeframes if timeframes else config.timeframes
        self.trend_data = {}
        self.analyzers = {}
        self.manual_data = data or {}
    
    def analyze_all_timeframes(self):
        """Analyze trends in all configured timeframes."""
        logger.progress(f"Analyzing {self.pair} across multiple timeframes")
        
        for tf_name, tf_interval in self.timeframes.items():
            try:
                logger.info(f"Analyzing {tf_name} ({tf_interval})")
                
                # Get data for this timeframe (from manual data or API)
                if tf_interval in self.manual_data:
                    df = self.manual_data[tf_interval]
                else:
                    df = api_manager.get_forex_data(
                        self.pair,
                        tf_interval,
                        outputsize="full"
                    )
                
                # Ensure we have enough data
                min_candles = config.get_trading_config("data.min_candles_required")
                if len(df) < min_candles:
                    logger.warning(f"Insufficient data for {tf_name}: {len(df)} candles")
                    continue
                
                # Create analyzer
                analyzer = IndicatorAnalyzer(df)
                self.analyzers[tf_name] = analyzer
                
                # Analyze trend
                trend_info = self._analyze_timeframe(tf_name, analyzer)
                self.trend_data[tf_name] = trend_info
                
                logger.success(
                    f"{tf_name}: {trend_info.direction.upper()} "
                    f"(strength: {trend_info.strength:.1f}, "
                    f"confidence: {trend_info.confidence:.2f})"
                )
            
            except Exception as e:
                logger.error(f"Failed to analyze {tf_name}: {e}")
                continue
        
        if not self.trend_data:
            raise RuntimeError(f"Failed to analyze any timeframe for {self.pair}")
    
    def _analyze_timeframe(
        self,
        tf_name: str,
        analyzer: IndicatorAnalyzer
    ) -> TrendInfo:
        """
        Analyze trend for a specific timeframe.
        
        Args:
            tf_name: Timeframe name
            analyzer: Indicator analyzer instance
        
        Returns:
            TrendInfo object
        """
        # Get trend direction from EMAs
        direction = analyzer.get_trend_direction()
        
        # Get trend strength from ADX
        strength = analyzer.get_trend_strength()
        
        # Check EMA alignment
        latest = analyzer.get_latest_values()
        ema_12 = latest['ema_12']
        ema_26 = latest['ema_26']
        ema_50 = latest['ema_50']
        
        if direction == "bullish":
            ema_alignment = ema_12 > ema_26 > ema_50
        elif direction == "bearish":
            ema_alignment = ema_12 < ema_26 < ema_50
        else:
            ema_alignment = False
        
        # Calculate confidence score
        confidence = self._calculate_confidence(
            direction, strength, ema_alignment, latest
        )
        
        return TrendInfo(
            timeframe=tf_name,
            direction=direction,
            strength=strength,
            confidence=confidence,
            ema_alignment=ema_alignment
        )
    
    def _calculate_confidence(
        self,
        direction: str,
        strength: float,
        ema_alignment: bool,
        indicators: dict
    ) -> float:
        """
        Calculate confidence score for trend.
        
        Args:
            direction: Trend direction
            strength: ADX value
            ema_alignment: Whether EMAs are aligned
            indicators: Latest indicator values
        
        Returns:
            Confidence score (0-1)
        """
        score = 0.0
        
        # ADX contribution (0-0.4)
        adx_threshold = config.get_trading_config("indicators.adx_threshold")
        if strength >= adx_threshold:
            score += 0.4 * min(strength / 50, 1.0)
        
        # EMA alignment (0-0.3)
        if ema_alignment:
            score += 0.3
        
        # MACD confirmation (0-0.2)
        macd = indicators.get('macd', 0)
        if direction == "bullish" and macd > 0:
            score += 0.2
        elif direction == "bearish" and macd < 0:
            score += 0.2
        
        # RSI zone (0-0.1)
        rsi = indicators.get('rsi', 50)
        if direction == "bullish" and 40 <= rsi <= 70:
            score += 0.1
        elif direction == "bearish" and 30 <= rsi <= 60:
            score += 0.1
        
        return min(score, 1.0)
    
    def get_primary_trend(self) -> TrendInfo:
        """
        Get primary trend (from H4 or longest timeframe).
        
        Returns:
            TrendInfo for primary timeframe
        """
        # Prefer H4 (medium timeframe)
        if "medium" in self.trend_data:
            return self.trend_data["medium"]
        
        # Fallback to any available
        if self.trend_data:
            return list(self.trend_data.values())[0]
        
        raise RuntimeError("No trend data available")
    
    def is_aligned(self, min_timeframes: int = 2) -> bool:
        """
        Check if trends are aligned across timeframes.
        
        Args:
            min_timeframes: Minimum number of timeframes that must agree
        
        Returns:
            True if aligned
        """
        if len(self.trend_data) < min_timeframes:
            return False
        
        directions = [t.direction for t in self.trend_data.values()]
        
        # Count bullish and bearish
        bullish_count = directions.count("bullish")
        bearish_count = directions.count("bearish")
        
        return (
            bullish_count >= min_timeframes or
            bearish_count >= min_timeframes
        )
    
    def get_alignment_score(self) -> float:
        """
        Get alignment score across all timeframes.
        
        Returns:
            Score from 0 to 1
        """
        if not self.trend_data:
            return 0.0
        
        directions = [t.direction for t in self.trend_data.values()]
        total = len(directions)
        
        bullish_count = directions.count("bullish")
        bearish_count = directions.count("bearish")
        
        # Return proportion of aligned timeframes
        max_aligned = max(bullish_count, bearish_count)
        
        return max_aligned / total if total > 0 else 0.0
    
    def get_consensus_direction(self) -> str:
        """
        Get consensus direction across timeframes.
        
        Returns:
            "bullish", "bearish", or "neutral"
        """
        if not self.trend_data:
            return "neutral"
        
        directions = [t.direction for t in self.trend_data.values()]
        
        bullish_count = directions.count("bullish")
        bearish_count = directions.count("bearish")
        
        if bullish_count > bearish_count:
            return "bullish"
        elif bearish_count > bullish_count:
            return "bearish"
        else:
            return "neutral"
    
    def get_summary(self) -> Dict:
        """Get summary of trend analysis."""
        return {
            'pair': self.pair,
            'primary_trend': self.get_primary_trend(),
            'consensus': self.get_consensus_direction(),
            'alignment_score': self.get_alignment_score(),
            'is_aligned': self.is_aligned(),
            'timeframes': self.trend_data
        }
