"""
Alpha Vantage API client for forex data and technical indicators.
"""
from typing import Dict, Any, Optional
import pandas as pd

from .base_api import BaseAPI
from ..utils.logger import logger


class AlphaVantageAPI(BaseAPI):
    """Alpha Vantage API client."""
    
    def __init__(self, api_key: str, rate_limit: int = 5):
        super().__init__(
            api_key=api_key,
            base_url="https://www.alphavantage.co/query",
            rate_limit=rate_limit
        )
    
    def _is_error_response(self, data: Dict[str, Any]) -> bool:
        """Check if response contains an error."""
        return "Error Message" in data or "Note" in data
    
    def _extract_error_message(self, data: Dict[str, Any]) -> str:
        """Extract error message from response."""
        return data.get("Error Message") or data.get("Note", "Unknown error")
    
    def get_forex_data(
        self,
        pair: str,
        interval: str,
        outputsize: str = "full"
    ) -> pd.DataFrame:
        """
        Get forex OHLCV data.
        
        Args:
            pair: Currency pair (e.g., "EURUSD")
            interval: Time interval (1min, 5min, 15min, 30min, 60min, daily, weekly, monthly)
            outputsize: "compact" (100 points) or "full" (full history)
        
        Returns:
            DataFrame with OHLCV data
        """
        # Convert pair format (EURUSD -> EUR/USD)
        from_currency = pair[:3]
        to_currency = pair[3:]
        
        # Map common interval names to Alpha Vantage format
        interval_map = {
            "H1": "60min",
            "H4": "240min",  # Note: Alpha Vantage doesn't support 4hour, we'll use daily for H4
            "D1": "daily",
            "1h": "60min",
            "4h": "240min",
            "1d": "daily"
        }
        
        # Convert interval if needed
        av_interval = interval_map.get(interval, interval)
        
        # Note: Alpha Vantage doesn't support 240min (4 hours)
        # For H4, we'll use daily data and resample
        if av_interval == "240min":
            av_interval = "60min"  # Get hourly data and we'll resample to 4H
        
        # Determine function based on interval
        if av_interval in ["1min", "5min", "15min", "30min", "60min"]:
            function = "FX_INTRADAY"
            params = {
                "function": function,
                "from_symbol": from_currency,
                "to_symbol": to_currency,
                "interval": av_interval,
                "outputsize": outputsize,
                "apikey": self.api_key
            }
        elif av_interval == "daily":
            function = "FX_DAILY"
            params = {
                "function": function,
                "from_symbol": from_currency,
                "to_symbol": to_currency,
                "outputsize": outputsize,
                "apikey": self.api_key
            }
        else:
            raise ValueError(f"Unsupported interval: {interval} (mapped to {av_interval})")
        
        logger.info(f"Fetching {pair} data for {interval} interval")
        
        # Dynamic cache duration based on interval
        cache_dur = 900 # Default 15m
        if interval == "D1": cache_dur = 43200 # 12 hours
        elif interval == "H4": cache_dur = 14400 # 4 hours
        elif interval == "H1": cache_dur = 1800 # 30 mins
        
        data = self._make_request("", params, cache_duration=cache_dur)
        
        # Parse response
        time_series_key = None
        for key in data.keys():
            if "Time Series" in key:
                time_series_key = key
                break
        
        if not time_series_key:
            raise ValueError(f"No time series data found in response")
        
        # Convert to DataFrame
        df = pd.DataFrame.from_dict(data[time_series_key], orient='index')
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        
        # Rename columns
        df.columns = ['open', 'high', 'low', 'close']
        df = df.astype(float)
        
        # If we requested H4 but got hourly data, resample to 4H
        if interval == "H4" and av_interval == "60min":
            logger.info(f"Resampling hourly data to 4H for {pair}")
            df = df.resample('4H').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last'
            }).dropna()
        
        logger.success(f"Retrieved {len(df)} candles for {pair}")
        return df
    
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
            indicator: Indicator name (EMA, RSI, MACD, ATR, etc.)
            interval: Time interval
            **kwargs: Additional indicator parameters
        
        Returns:
            DataFrame with indicator values
        """
        from_currency = pair[:3]
        to_currency = pair[3:]
        
        params = {
            "function": indicator.upper(),
            "from_symbol": from_currency,
            "to_symbol": to_currency,
            "interval": interval,
            "apikey": self.api_key,
            **kwargs
        }
        
        logger.info(f"Fetching {indicator} for {pair}")
        data = self._make_request("", params)
        
        # Find technical analysis key
        tech_key = None
        for key in data.keys():
            if "Technical Analysis" in key:
                tech_key = key
                break
        
        if not tech_key:
            raise ValueError(f"No technical analysis data found")
        
        # Convert to DataFrame
        df = pd.DataFrame.from_dict(data[tech_key], orient='index')
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df = df.astype(float)
        
        return df
    
    def get_ema(self, pair: str, interval: str, period: int = 12) -> pd.DataFrame:
        """Get EMA indicator."""
        return self.get_indicator(
            pair, "EMA", interval,
            time_period=period,
            series_type="close"
        )
    
    def get_rsi(self, pair: str, interval: str, period: int = 14) -> pd.DataFrame:
        """Get RSI indicator."""
        return self.get_indicator(
            pair, "RSI", interval,
            time_period=period,
            series_type="close"
        )
    
    def get_macd(self, pair: str, interval: str) -> pd.DataFrame:
        """Get MACD indicator."""
        return self.get_indicator(
            pair, "MACD", interval,
            series_type="close"
        )
    
    def get_atr(self, pair: str, interval: str, period: int = 14) -> pd.DataFrame:
        """Get ATR indicator."""
        return self.get_indicator(
            pair, "ATR", interval,
            time_period=period
        )
