"""
Twelvedata API client for forex data and technical indicators.
"""
from typing import Dict, Any, Optional
import pandas as pd

from .base_api import BaseAPI
from ..utils.logger import logger


class TwelvedataAPI(BaseAPI):
    """Twelvedata API client."""
    
    def __init__(self, api_key: str, rate_limit: int = 8):
        super().__init__(
            api_key=api_key,
            base_url="https://api.twelvedata.com",
            rate_limit=rate_limit
        )
    
    def _is_error_response(self, data: Dict[str, Any]) -> bool:
        """Check if response contains an error."""
        return "status" in data and data["status"] == "error"
    
    def _extract_error_message(self, data: Dict[str, Any]) -> str:
        """Extract error message from response."""
        return data.get("message", "Unknown error")
    
    def get_forex_data(
        self,
        pair: str,
        interval: str,
        outputsize: str = "full"  # Can be "full" or "compact" for Alpha Vantage, or integer for Twelvedata
    ) -> pd.DataFrame:
        """
        Get forex OHLCV data.
        
        Args:
            pair: Currency pair (e.g., "EUR/USD")
            interval: Time interval (1min, 5min, 15min, 30min, 1h, 4h, 1day, etc.)
            outputsize: Number of data points (max 5000)
        
        Returns:
            DataFrame with OHLCV data
        """
        # Convert interval format
        interval_map = {
            "60min": "1h",
            "H1": "1h",
            "H4": "4h",
            "D1": "1day",
            "daily": "1day"
        }
        interval = interval_map.get(interval, interval)
        
        # Format pair (EURUSD -> EUR/USD)
        if "/" not in pair:
            pair = f"{pair[:3]}/{pair[3:]}"
        
        # Convert outputsize to integer if it's a string
        if isinstance(outputsize, str):
            outputsize = 5000 if outputsize == "full" else 100
        
        params = {
            "symbol": pair,
            "interval": interval,
            "outputsize": outputsize,
            "apikey": self.api_key
        }
        
        logger.info(f"Fetching {pair} data for {interval} interval")
        
        # Dynamic cache duration based on interval
        cache_dur = 900 # Default 15m
        if interval == "D1": cache_dur = 43200 # 12 hours
        elif interval == "H4": cache_dur = 14400 # 4 hours
        elif interval == "H1": cache_dur = 1800 # 30 mins
        
        data = self._make_request("time_series", params, cache_duration=cache_dur)
        
        if "values" not in data:
            raise ValueError("No time series data in response")
        
        # Convert to DataFrame
        df = pd.DataFrame(data["values"])
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime')
        df = df.sort_index()
        
        # Convert to float and rename columns
        for col in ['open', 'high', 'low', 'close']:
            if col in df.columns:
                df[col] = df[col].astype(float)
        
        if 'volume' in df.columns:
            df['volume'] = df['volume'].astype(float)
        
        logger.success(f"Retrieved {len(df)} candles for {pair}")
        return df[['open', 'high', 'low', 'close']]
    
    def get_indicator(
        self,
        pair: str,
        indicator: str,
        interval: str,
        **kwargs
    ) -> pd.DataFrame:
        """
        Get technical indicator data.
        
        Args:
            pair: Currency pair
            indicator: Indicator name (ema, rsi, macd, atr, etc.)
            interval: Time interval
            **kwargs: Additional indicator parameters
        
        Returns:
            DataFrame with indicator values
        """
        # Convert interval format
        interval_map = {
            "60min": "1h",
            "H1": "1h",
            "H4": "4h",
            "D1": "1day",
            "daily": "1day"
        }
        interval = interval_map.get(interval, interval)
        
        # Format pair
        if "/" not in pair:
            pair = f"{pair[:3]}/{pair[3:]}"
        
        params = {
            "symbol": pair,
            "interval": interval,
            "apikey": self.api_key,
            **kwargs
        }
        
        logger.info(f"Fetching {indicator} for {pair}")
        data = self._make_request(indicator.lower(), params)
        
        if "values" not in data:
            raise ValueError("No indicator data in response")
        
        # Convert to DataFrame
        df = pd.DataFrame(data["values"])
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime')
        df = df.sort_index()
        
        # Convert to float
        for col in df.columns:
            try:
                df[col] = df[col].astype(float)
            except:
                pass
        
        return df
    
    def get_ema(self, pair: str, interval: str, period: int = 12) -> pd.DataFrame:
        """Get EMA indicator."""
        return self.get_indicator(
            pair, "ema", interval,
            time_period=period
        )
    
    def get_rsi(self, pair: str, interval: str, period: int = 14) -> pd.DataFrame:
        """Get RSI indicator."""
        return self.get_indicator(
            pair, "rsi", interval,
            time_period=period
        )
    
    def get_macd(self, pair: str, interval: str) -> pd.DataFrame:
        """Get MACD indicator."""
        return self.get_indicator(
            pair, "macd", interval
        )
    
    def get_atr(self, pair: str, interval: str, period: int = 14) -> pd.DataFrame:
        """Get ATR indicator."""
        return self.get_indicator(
            pair, "atr", interval,
            time_period=period
        )
