"""
API manager with automatic fallback between providers.
"""
from typing import Optional, List
import pandas as pd

from .alpha_vantage import AlphaVantageAPI
from .twelvedata import TwelvedataAPI
from ..utils.config import config
from ..utils.logger import logger


class APIManager:
    """Manages multiple API providers with automatic fallback."""
    
    def __init__(self):
        self.providers = {}
        self.request_count = 0
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize available API providers."""
        # Try to initialize Alpha Vantage
        try:
            api_config = config.get_api_config("alpha_vantage")
            api_key = api_config["api_key"]
            if api_key and "YOUR_" not in api_key:
                self.providers["alpha_vantage"] = AlphaVantageAPI(
                    api_key=api_key,
                    rate_limit=api_config.get("rate_limit_per_minute", 5)
                )
                logger.info("✅ Alpha Vantage API initialized")
        except Exception as e:
            logger.warning(f"Alpha Vantage not available: {e}")
        
        # Try to initialize Twelvedata
        try:
            api_config = config.get_api_config("twelvedata")
            api_key = api_config["api_key"]
            if api_key and "YOUR_" not in api_key:
                self.providers["twelvedata"] = TwelvedataAPI(
                    api_key=api_key,
                    rate_limit=api_config.get("rate_limit_per_minute", 8)
                )
                logger.info("✅ Twelvedata API initialized")
        except Exception as e:
            logger.warning(f"Twelvedata not available: {e}")
        
        if not self.providers:
            raise RuntimeError(
                "No API providers available. Please configure at least one API key in config/api_keys.json"
            )
        
        logger.success(f"API Manager initialized with {len(self.providers)} provider(s)")
    
    def _get_provider_order(self) -> List[str]:
        """Get ordered list of providers to try."""
        primary = config.primary_api_provider
        fallbacks = config.fallback_api_providers
        
        # Build order: primary first, then fallbacks, then any others
        order = []
        if primary in self.providers:
            order.append(primary)
        
        for fallback in fallbacks:
            if fallback in self.providers and fallback not in order:
                order.append(fallback)
        
        # Add any remaining providers
        for provider in self.providers:
            if provider not in order:
                order.append(provider)
        
        return order
    
    def get_forex_data(
        self,
        pair: str,
        interval: str,
        outputsize: str = "full"
    ) -> pd.DataFrame:
        """
        Get forex data with automatic fallback.
        
        Args:
            pair: Currency pair (e.g., "EURUSD")
            interval: Time interval
            outputsize: Data size
        
        Returns:
            DataFrame with OHLCV data
        """
        provider_order = self._get_provider_order()
        
        for provider_name in provider_order:
            try:
                logger.info(f"Trying {provider_name} for {pair} data")
                provider = self.providers[provider_name]
                self.request_count += 1
                logger.debug(f"API Requests this session: {self.request_count}")
                return provider.get_forex_data(pair, interval, outputsize)
            
            except Exception as e:
                logger.warning(f"{provider_name} failed: {e}")
                if provider_name == provider_order[-1]:
                    # Last provider failed
                    raise RuntimeError(
                        f"All API providers failed to retrieve data for {pair}"
                    ) from e
                else:
                    logger.info(f"Falling back to next provider...")
                    continue
    
    def get_indicator(
        self,
        pair: str,
        indicator: str,
        interval: str,
        **kwargs
    ) -> pd.DataFrame:
        """
        Get technical indicator with automatic fallback.
        
        Args:
            pair: Currency pair
            indicator: Indicator name
            interval: Time interval
            **kwargs: Additional parameters
        
        Returns:
            DataFrame with indicator values
        """
        provider_order = self._get_provider_order()
        
        for provider_name in provider_order:
            try:
                logger.info(f"Trying {provider_name} for {indicator}")
                provider = self.providers[provider_name]
                return provider.get_indicator(pair, indicator, interval, **kwargs)
            
            except Exception as e:
                logger.warning(f"{provider_name} failed: {e}")
                if provider_name == provider_order[-1]:
                    # Last provider failed - return None to trigger manual calculation
                    logger.warning(f"All providers failed for {indicator}, will calculate manually")
                    return None
                else:
                    continue
    
    def clear_all_caches(self):
        """Clear cache for all providers."""
        for provider in self.providers.values():
            provider.clear_cache()
        logger.success("All caches cleared")


# Global API manager instance
api_manager = APIManager()
