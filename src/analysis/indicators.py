"""
Technical indicators calculation with fallback to manual computation.
"""
import pandas as pd
import numpy as np
from typing import Optional, Tuple

from ..utils.config import config
from ..utils.logger import logger


class TechnicalIndicators:
    """Calculate technical indicators manually if API doesn't provide them."""
    
    @staticmethod
    def calculate_ema(data: pd.Series, period: int) -> pd.Series:
        """
        Calculate Exponential Moving Average.
        
        Args:
            data: Price series
            period: EMA period
        
        Returns:
            EMA series
        """
        return data.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def calculate_sma(data: pd.Series, period: int) -> pd.Series:
        """Calculate Simple Moving Average."""
        return data.rolling(window=period).mean()
    
    @staticmethod
    def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index.
        
        Args:
            data: Price series
            period: RSI period (default 14)
        
        Returns:
            RSI series
        """
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def calculate_macd(
        data: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate MACD (Moving Average Convergence Divergence).
        
        Args:
            data: Price series
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period
        
        Returns:
            Tuple of (MACD line, Signal line, Histogram)
        """
        ema_fast = TechnicalIndicators.calculate_ema(data, fast)
        ema_slow = TechnicalIndicators.calculate_ema(data, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def calculate_atr(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """
        Calculate Average True Range.
        
        Args:
            high: High price series
            low: Low price series
            close: Close price series
            period: ATR period
        
        Returns:
            ATR series
        """
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        
        return atr
    
    @staticmethod
    def calculate_bollinger_bands(
        data: pd.Series,
        period: int = 20,
        std_dev: float = 2.0
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands.
        
        Args:
            data: Price series
            period: Moving average period
            std_dev: Standard deviation multiplier
        
        Returns:
            Tuple of (Upper band, Middle band, Lower band)
        """
        middle_band = TechnicalIndicators.calculate_sma(data, period)
        std = data.rolling(window=period).std()
        
        upper_band = middle_band + (std * std_dev)
        lower_band = middle_band - (std * std_dev)
        
        return upper_band, middle_band, lower_band
    
    @staticmethod
    def calculate_adx(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Average Directional Index (trend strength).
        
        Args:
            high: High price series
            low: Low price series
            close: Close price series
            period: ADX period
        
        Returns:
            Tuple of (ADX, +DI, -DI)
        """
        # Calculate +DM and -DM
        # Use simple difference for efficiency
        high_diff = high.diff()
        low_diff = -low.diff()
        
        # +DM: High moved up and more than Low moved down
        plus_dm = pd.Series(0.0, index=high.index)
        mask_plus = (high_diff > low_diff) & (high_diff > 0)
        plus_dm[mask_plus] = high_diff[mask_plus]
        
        # -DM: Low moved down and more than High moved up
        minus_dm = pd.Series(0.0, index=low.index)
        mask_minus = (low_diff > high_diff) & (low_diff > 0)
        minus_dm[mask_minus] = low_diff[mask_minus]
        
        # Calculate ATR (True Range first)
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Smooth TR, +DM, -DM using Wilder's Smoothing (alpha=1/period)
        atr = tr.ewm(alpha=1/period, adjust=False).mean()
        plus_dm_smooth = plus_dm.ewm(alpha=1/period, adjust=False).mean()
        minus_dm_smooth = minus_dm.ewm(alpha=1/period, adjust=False).mean()
        
        # Calculate +DI and -DI
        plus_di = (plus_dm_smooth / (atr + 1e-6)) * 100
        minus_di = (minus_dm_smooth / (atr + 1e-6)) * 100
        
        # Calculate DX
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-6)) * 100
        
        # Calculate ADX (Smooth DX)
        adx = dx.ewm(alpha=1/period, adjust=False).mean()
        
        return adx, plus_di, minus_di

        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        # Calculate DX
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        
        # Calculate ADX
        adx = dx.rolling(window=period).mean()
        
        return adx

    @staticmethod
    def calculate_hurst(data: pd.Series, period: int = 100) -> float:
        """
        Calculate the Hurst Exponent to identify the market regime.
        H < 0.5: Mean Reverting
        H = 0.5: Random Walk
        H > 0.5: Trending
        
        Args:
            data: Price series (e.g., close)
            period: Lookback period for R/S calculation (default 100)
            
        Returns:
            Hurst Exponent (float)
        """
        if len(data) < period:
            return 0.5 # Neutral fallback
            
        series = data.tail(period).values
        lags = range(2, period // 2)
        
        # Calculate variates of log differences
        tau = [np.sqrt(np.std(np.subtract(series[lag:], series[:-lag]))) for lag in lags]
        
        # Fit log(tau) vs log(lags)
        reg = np.polyfit(np.log(lags), np.log(tau), 1)
        
        # Hurst exponent is the slope
        hurst = reg[0] * 2
        return float(hurst)

    @staticmethod
    def calculate_vwap(df: pd.DataFrame) -> pd.Series:
        """
        Calculate Volume Weighted Average Price (VWAP).
        """
        # Average price
        tp = (df['high'] + df['low'] + df['close']) / 3
        # Volume * Price
        v_p = tp * df['volume']
        # Cumulative Sum
        v_p_cum = v_p.cumsum()
        vol_cum = df['volume'].cumsum()
        vwap = v_p_cum / vol_cum
        return vwap

    @staticmethod
    def calculate_supertrend(
        high: pd.Series, 
        low: pd.Series, 
        close: pd.Series, 
        period: int = 10, 
        multiplier: float = 3.0
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Calculate SuperTrend.
        Returns: (SuperTrend values, Trend Direction: 1 for bullish, -1 for bearish)
        """
        atr = TechnicalIndicators.calculate_atr(high, low, close, period)
        
        # High-Low Average
        hl2 = (high + low) / 2
        
        basic_upperband = hl2 + (multiplier * atr)
        basic_lowerband = hl2 - (multiplier * atr)
        
        upperband = basic_upperband.copy()
        lowerband = basic_lowerband.copy()
        
        # Iterative version to ensure correctness (Standard SuperTrend logic)
        st = np.zeros(len(close))
        direc = np.ones(len(close))
        
        # Ensure we work with copies to avoid read-only issues
        upperband_vals = basic_upperband.values.copy()
        lowerband_vals = basic_lowerband.values.copy()
        close_vals = close.values
        
        for i in range(period, len(close)):
            # Upper Band logic
            if close_vals[i-1] <= upperband_vals[i-1]:
                upperband_vals[i] = min(upperband_vals[i], upperband_vals[i-1])
            else:
                upperband_vals[i] = upperband_vals[i]
                
            # Lower Band logic
            if close_vals[i-1] >= lowerband_vals[i-1]:
                lowerband_vals[i] = max(lowerband_vals[i], lowerband_vals[i-1])
            else:
                lowerband_vals[i] = lowerband_vals[i]
            
            # Trend calculation
            if close_vals[i] > upperband_vals[i]:
                direc[i] = 1
            elif close_vals[i] < lowerband_vals[i]:
                direc[i] = -1
            else:
                direc[i] = direc[i-1]
                
            st[i] = upperband_vals[i] if direc[i] == -1 else lowerband_vals[i]
            
        return pd.Series(st, index=close.index), pd.Series(direc, index=close.index)

    @staticmethod
    def calculate_atr_normalized(atr: pd.Series, close: pd.Series) -> pd.Series:
        """Calculate ATR as a percentage of price (normalized volatility)."""
        return (atr / close) * 100


class IndicatorAnalyzer:
    """Analyze indicators and provide trading signals."""
    
    def __init__(self, df: pd.DataFrame):
        """
        Initialize with OHLCV data.
        
        Args:
            df: DataFrame with columns: open, high, low, close
        """
        self.df = df.copy()
        self.indicators = {}
        self._calculate_all_indicators()
    
    def _calculate_all_indicators(self):
        """Calculate all required indicators."""
        logger.progress("Calculating technical indicators")
        
        # Get configuration
        ema_periods = config.get_trading_config("indicators.ema_periods")
        rsi_period = config.get_trading_config("indicators.rsi_period")
        atr_period = config.get_trading_config("indicators.atr_period")
        adx_period = config.get_trading_config("indicators.adx_period")
        
        # EMAs
        periods_to_calc = set(ema_periods + [9, 15, 200]) # Literature-backed periods
        for period in periods_to_calc:
            self.indicators[f'ema_{period}'] = TechnicalIndicators.calculate_ema(
                self.df['close'], period
            )
        
        # RSI
        self.indicators['rsi'] = TechnicalIndicators.calculate_rsi(
            self.df['close'], rsi_period
        )
        
        # MACD
        macd_line, signal_line, histogram = TechnicalIndicators.calculate_macd(
            self.df['close']
        )
        self.indicators['macd'] = macd_line
        self.indicators['macd_signal'] = signal_line
        self.indicators['macd_histogram'] = histogram
        
        # ATR
        self.indicators['atr'] = TechnicalIndicators.calculate_atr(
            self.df['high'], self.df['low'], self.df['close'], atr_period
        )
        
        # ADX
        adx, plus_di, minus_di = TechnicalIndicators.calculate_adx(
            self.df['high'], self.df['low'], self.df['close'], adx_period
        )
        self.indicators['adx'] = adx
        self.indicators['plus_di'] = plus_di
        self.indicators['minus_di'] = minus_di
        
        # Phase 10: Volume Confirmation (Literature requirement)
        if 'volume' in self.df.columns:
            self.indicators['volume_avg_20'] = self.df['volume'].rolling(20).mean()
            self.indicators['volume_ratio'] = self.df['volume'] / (self.indicators['volume_avg_20'] + 1e-6)
        
        # Hurst Exponent (Regime Detection)
        self.indicators['hurst'] = TechnicalIndicators.calculate_hurst(
            self.df['close'], period=100
        )
        
        # Bollinger Bands
        upper, middle, lower = TechnicalIndicators.calculate_bollinger_bands(
            self.df['close']
        )
        self.indicators['bb_upper'] = upper
        self.indicators['bb_middle'] = middle
        self.indicators['bb_lower'] = lower

        # --- INSTITUTIONAL UPGRADE START ---
        
        # VWAP
        self.indicators['vwap'] = TechnicalIndicators.calculate_vwap(self.df)
        
        # SuperTrend
        st_vals, st_dir = TechnicalIndicators.calculate_supertrend(
            self.df['high'], self.df['low'], self.df['close']
        )
        self.indicators['supertrend'] = st_vals
        self.indicators['supertrend_dir'] = st_dir # 1 for bulls, -1 for bears
        
        # Normalized ATR (Institutional standard for comparing volatility)
        self.indicators['atr_norm'] = TechnicalIndicators.calculate_atr_normalized(
            self.indicators['atr'], self.df['close']
        )
        
        # --- INSTITUTIONAL UPGRADE END ---
        
        # ML Features: Wick Ratio (last 3 candles)
        last_3 = self.df.tail(3)
        wicks = (last_3['high'] - last_3[['open', 'close']].max(axis=1)).sum() + \
                (last_3[['open', 'close']].min(axis=1) - last_3['low']).sum()
        bodies = (last_3['open'] - last_3['close']).abs().sum()
        self.indicators['wick_ratio'] = wicks / (bodies + 1e-6)
        
        # ML Features: ATR Average (last 20)
        self.indicators['atr_avg'] = self.indicators['atr'].rolling(20).mean()
        
        # ML Features: Successive Movements (Proportion of same-direction candles in last 5)
        last_5 = self.df.tail(5)
        self.indicators['successive_move'] = (last_5['close'] > last_5['open']).astype(int).mean()
        
        logger.success("All indicators calculated")
    
    def get_latest_values(self) -> dict:
        """Get latest values of all indicators."""
        latest = {}
        for name, value in self.indicators.items():
            if isinstance(value, pd.Series):
                latest[name] = value.iloc[-1] if not value.empty else None
            else:
                # Handle scalar values (ML features)
                latest[name] = value
        
        # Add current price
        latest['current_price'] = self.df['close'].iloc[-1]
        latest['current_high'] = self.df['high'].iloc[-1]
        latest['current_low'] = self.df['low'].iloc[-1]
        
        return latest
    
    def get_trend_direction(self) -> str:
        """
        Determine trend direction based on EMAs and Price.
        
        Returns:
            "bullish", "bearish", or "neutral"
        """
        ema_12 = self.indicators['ema_12'].iloc[-1]
        ema_26 = self.indicators['ema_26'].iloc[-1]
        ema_50 = self.indicators['ema_50'].iloc[-1]
        price = self.df['close'].iloc[-1]
        
        # Bullish: 12 > 26 and price > 50 (Strong) OR 12 > 26 > 50 (Mega Strong)
        if ema_12 > ema_26 and price > ema_50:
            return "bullish"
        # Bearish: 12 < 26 and price < 50 (Strong) OR 12 < 26 < 50 (Mega Strong)
        elif ema_12 < ema_26 and price < ema_50:
            return "bearish"
        else:
            return "neutral"
    
    def get_trend_strength(self) -> float:
        """
        Get trend strength from ADX.
        
        Returns:
            ADX value (0-100)
        """
        return self.indicators['adx'].iloc[-1]
    
    def is_rsi_overbought(self) -> bool:
        """Check if RSI is in overbought zone."""
        rsi_overbought = config.get_trading_config("indicators.rsi_overbought")
        return self.indicators['rsi'].iloc[-1] > rsi_overbought
    
    def is_rsi_oversold(self) -> bool:
        """Check if RSI is in oversold zone."""
        rsi_oversold = config.get_trading_config("indicators.rsi_oversold")
        return self.indicators['rsi'].iloc[-1] < rsi_oversold
    
    def get_rsi_zone(self) -> str:
        """Get RSI zone classification."""
        rsi = self.indicators['rsi'].iloc[-1]
        
        if rsi > 70:
            return "overbought"
        elif rsi < 30:
            return "oversold"
        elif 40 <= rsi <= 60:
            return "neutral"
        else:
            return "normal"
