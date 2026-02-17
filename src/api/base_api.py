"""
Base API client with rate limiting and error handling.
"""
import time
import requests
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import json
from diskcache import Cache

from ..utils.logger import logger


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, calls_per_minute: int):
        self.calls_per_minute = calls_per_minute
        self.min_interval = 60.0 / calls_per_minute
        self.last_call = 0
    
    def wait_if_needed(self):
        """Wait if necessary to respect rate limit."""
        now = time.time()
        time_since_last = now - self.last_call
        
        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_call = time.time()


class BaseAPI(ABC):
    """Abstract base class for API clients."""
    
    def __init__(self, api_key: str, base_url: str, rate_limit: int):
        self.api_key = api_key
        self.base_url = base_url
        self.rate_limiter = RateLimiter(rate_limit)
        self.session = requests.Session()
        
        # Setup cache
        cache_dir = Path(__file__).parent.parent.parent / "data" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache = Cache(str(cache_dir))
    
    def _make_request(
        self,
        endpoint: str,
        params: Dict[str, Any],
        cache_duration: int = 900  # 15 minutes default
    ) -> Dict[str, Any]:
        """
        Make API request with rate limiting, caching, and error handling.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            cache_duration: Cache duration in seconds
        
        Returns:
            API response as dictionary
        """
        # Create cache key
        cache_key = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        
        # Check cache
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"Cache hit for {endpoint}")
            return cached_data
        
        # Rate limiting
        self.rate_limiter.wait_if_needed()
        
        # Make request
        try:
            logger.debug(f"API request: {endpoint} with params: {params}")
            response = self.session.get(
                f"{self.base_url}/{endpoint}",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API-specific errors
            if self._is_error_response(data):
                error_msg = self._extract_error_message(data)
                raise Exception(f"API error: {error_msg}")
            
            # Cache successful response
            self.cache.set(cache_key, data, expire=cache_duration)
            
            return data
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise
    
    @abstractmethod
    def _is_error_response(self, data: Dict[str, Any]) -> bool:
        """Check if response contains an error."""
        pass
    
    @abstractmethod
    def _extract_error_message(self, data: Dict[str, Any]) -> str:
        """Extract error message from response."""
        pass
    
    @abstractmethod
    def get_forex_data(
        self,
        pair: str,
        interval: str,
        outputsize: str = "full"
    ) -> Dict[str, Any]:
        """Get forex OHLCV data."""
        pass
    
    @abstractmethod
    def get_indicator(
        self,
        pair: str,
        indicator: str,
        interval: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Get technical indicator data."""
        pass
    
    def clear_cache(self):
        """Clear all cached data."""
        self.cache.clear()
        logger.info("Cache cleared")
