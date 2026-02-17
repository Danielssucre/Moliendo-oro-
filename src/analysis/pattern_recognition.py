"""
Support/Resistance detection and candlestick pattern recognition.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional

from ..utils.logger import logger


class SupportResistance:
    """Detect support and resistance levels."""
    
    @staticmethod
    def find_pivot_points(df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate pivot points for support/resistance.
        
        Args:
            df: DataFrame with OHLC data
        
        Returns:
            Dictionary with pivot levels
        """
        # Use previous day's data
        high = df['high'].iloc[-2]
        low = df['low'].iloc[-2]
        close = df['close'].iloc[-2]
        
        pivot = (high + low + close) / 3
        
        r1 = 2 * pivot - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)
        
        s1 = 2 * pivot - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (high - pivot)
        
        return {
            'pivot': pivot,
            'r1': r1, 'r2': r2, 'r3': r3,
            's1': s1, 's2': s2, 's3': s3
        }
    
    @staticmethod
    def find_swing_levels(
        df: pd.DataFrame,
        window: int = 20,
        num_levels: int = 3
    ) -> Dict[str, List[float]]:
        """
        Find swing high/low levels.
        
        Args:
            df: DataFrame with OHLC data
            window: Lookback window
            num_levels: Number of levels to return
        
        Returns:
            Dictionary with resistance and support levels
        """
        # Find swing highs
        highs = df['high'].rolling(window=window, center=True).max()
        swing_highs = df[df['high'] == highs]['high'].values
        
        # Find swing lows
        lows = df['low'].rolling(window=window, center=True).min()
        swing_lows = df[df['low'] == lows]['low'].values
        
        # Get unique levels and sort
        resistance_levels = sorted(set(swing_highs), reverse=True)[:num_levels]
        support_levels = sorted(set(swing_lows))[:num_levels]
        
        return {
            'resistance': resistance_levels,
            'support': support_levels
        }
    
    @staticmethod
    def find_nearest_level(
        price: float,
        levels: List[float],
        max_distance_pips: float = 50,
        pip_multiplier: float = 10000
    ) -> Optional[float]:
        """
        Find nearest support/resistance level to current price.
        
        Args:
            price: Current price
            levels: List of S/R levels
            max_distance_pips: Maximum distance in pips
            pip_multiplier: Multiplier to convert to pips
        
        Returns:
            Nearest level or None
        """
        if not levels:
            return None
        
        distances = [abs(price - level) for level in levels]
        min_distance = min(distances)
        
        # Convert to pips
        min_distance_pips = min_distance * pip_multiplier
        
        if min_distance_pips <= max_distance_pips:
            return levels[distances.index(min_distance)]
        
        return None


class CandlestickPatterns:
    """Detect candlestick patterns."""
    
    @staticmethod
    def is_bullish_engulfing(row_prev: pd.Series, row_curr: pd.Series) -> bool:
        """Detect bullish engulfing pattern."""
        # Previous candle is bearish
        prev_bearish = row_prev['close'] < row_prev['open']
        
        # Current candle is bullish
        curr_bullish = row_curr['close'] > row_curr['open']
        
        # Current body engulfs previous body
        engulfs = (
            row_curr['open'] < row_prev['close'] and
            row_curr['close'] > row_prev['open']
        )
        
        return prev_bearish and curr_bullish and engulfs
    
    @staticmethod
    def is_bearish_engulfing(row_prev: pd.Series, row_curr: pd.Series) -> bool:
        """Detect bearish engulfing pattern."""
        # Previous candle is bullish
        prev_bullish = row_prev['close'] > row_prev['open']
        
        # Current candle is bearish
        curr_bearish = row_curr['close'] < row_curr['open']
        
        # Current body engulfs previous body
        engulfs = (
            row_curr['open'] > row_prev['close'] and
            row_curr['close'] < row_prev['open']
        )
        
        return prev_bullish and curr_bearish and engulfs
    
    @staticmethod
    def is_hammer(row: pd.Series) -> bool:
        """Detect hammer pattern (bullish reversal)."""
        body = abs(row['close'] - row['open'])
        lower_shadow = min(row['open'], row['close']) - row['low']
        upper_shadow = row['high'] - max(row['open'], row['close'])
        
        # Lower shadow at least 2x body
        # Upper shadow very small
        return (
            lower_shadow >= 2 * body and
            upper_shadow <= body * 0.3 and
            body > 0
        )
    
    @staticmethod
    def is_shooting_star(row: pd.Series) -> bool:
        """Detect shooting star pattern (bearish reversal)."""
        body = abs(row['close'] - row['open'])
        lower_shadow = min(row['open'], row['close']) - row['low']
        upper_shadow = row['high'] - max(row['open'], row['close'])
        
        # Upper shadow at least 2x body
        # Lower shadow very small
        return (
            upper_shadow >= 2 * body and
            lower_shadow <= body * 0.3 and
            body > 0
        )
    
    @staticmethod
    def is_doji(row: pd.Series) -> bool:
        """Detect doji pattern (indecision)."""
        body = abs(row['close'] - row['open'])
        total_range = row['high'] - row['low']
        
        # Body is very small compared to range
        return body <= total_range * 0.1 if total_range > 0 else False
    
    @staticmethod
    def is_pin_bar_bullish(row: pd.Series) -> bool:
        """Detect bullish pin bar."""
        body = abs(row['close'] - row['open'])
        lower_shadow = min(row['open'], row['close']) - row['low']
        total_range = row['high'] - row['low']
        
        # Long lower shadow (rejection of lower prices)
        return (
            lower_shadow >= total_range * 0.6 and
            row['close'] > row['open']  # Bullish close
        )
    
    @staticmethod
    def is_pin_bar_bearish(row: pd.Series) -> bool:
        """Detect bearish pin bar."""
        body = abs(row['close'] - row['open'])
        upper_shadow = row['high'] - max(row['open'], row['close'])
        total_range = row['high'] - row['low']
        
        # Long upper shadow (rejection of higher prices)
        return (
            upper_shadow >= total_range * 0.6 and
            row['close'] < row['open']  # Bearish close
        )


class PatternRecognizer:
    """Recognize patterns in price data."""
    
    def __init__(self, pair: str, df: pd.DataFrame):
        """
        Initialize with OHLC data.
        
        Args:
            pair: Currency pair name
            df: DataFrame with OHLC data
        """
        self.pair = pair
        self.df = df.copy()
        self.pip_multiplier = 100 if "JPY" in pair.upper() else 10000
        self.patterns = self._detect_patterns()
        self.sr_levels = self._detect_sr_levels()
    
    def _detect_patterns(self) -> Dict[str, bool]:
        """Detect all candlestick patterns on latest candles."""
        if len(self.df) < 2:
            return {}
        
        curr = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        
        patterns = {
            'bullish_engulfing': CandlestickPatterns.is_bullish_engulfing(prev, curr),
            'bearish_engulfing': CandlestickPatterns.is_bearish_engulfing(prev, curr),
            'hammer': CandlestickPatterns.is_hammer(curr),
            'shooting_star': CandlestickPatterns.is_shooting_star(curr),
            'doji': CandlestickPatterns.is_doji(curr),
            'pin_bar_bullish': CandlestickPatterns.is_pin_bar_bullish(curr),
            'pin_bar_bearish': CandlestickPatterns.is_pin_bar_bearish(curr)
        }
        
        return patterns
    
    def _detect_sr_levels(self) -> Dict[str, any]:
        """Detect support and resistance levels."""
        pivot_levels = SupportResistance.find_pivot_points(self.df)
        swing_levels = SupportResistance.find_swing_levels(self.df)
        
        return {
            'pivot': pivot_levels,
            'swing': swing_levels
        }
    
    def get_bullish_patterns(self) -> List[str]:
        """Get list of detected bullish patterns."""
        bullish = ['bullish_engulfing', 'hammer', 'pin_bar_bullish']
        return [p for p in bullish if self.patterns.get(p, False)]
    
    def get_bearish_patterns(self) -> List[str]:
        """Get list of detected bearish patterns."""
        bearish = ['bearish_engulfing', 'shooting_star', 'pin_bar_bearish']
        return [p for p in bearish if self.patterns.get(p, False)]
    
    def get_nearest_support(self, price: float) -> Optional[float]:
        """Get nearest support level below current price."""
        all_supports = (
            [self.sr_levels['pivot']['s1'], 
             self.sr_levels['pivot']['s2'],
             self.sr_levels['pivot']['s3']] +
            self.sr_levels['swing']['support']
        )
        
        # Filter supports below price
        supports_below = [s for s in all_supports if s < price]
        
        return SupportResistance.find_nearest_level(
            price, supports_below, pip_multiplier=self.pip_multiplier
        )
    
    def get_nearest_resistance(self, price: float) -> Optional[float]:
        """Get nearest resistance level above current price."""
        all_resistances = (
            [self.sr_levels['pivot']['r1'],
             self.sr_levels['pivot']['r2'],
             self.sr_levels['pivot']['r3']] +
            self.sr_levels['swing']['resistance']
        )
        
        # Filter resistances above price
        resistances_above = [r for r in all_resistances if r > price]
        
        return SupportResistance.find_nearest_level(
            price, resistances_above, pip_multiplier=self.pip_multiplier
        )
