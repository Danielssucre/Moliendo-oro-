"""
Configuration loader for the trading agent system.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any


class Config:
    """Singleton configuration manager."""
    
    _instance = None
    _config_dir = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        # Determine config directory - go up from src/utils to project root
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent  # Go up from src/nanobot/utils to project root
        self._config_dir = project_root / "config"
        
        # Load configurations
        self.api_keys = self._load_json("api_keys.json")
        self.trading = self._load_json("trading_config.json")
        
        # Apply strategy profile overrides
        self._apply_profile_overrides()
        
        self._initialized = True
    
    def reload(self):
        """Reload configuration from files."""
        self.api_keys = self._load_json("api_keys.json")
        self.trading = self._load_json("trading_config.json")
        self._apply_profile_overrides()
        
    def _apply_profile_overrides(self):
        """Apply overrides from the active strategy profile."""
        active_profile = self.trading.get("active_profile")
        profiles = self.trading.get("profiles", {})
        
        if active_profile and active_profile in profiles:
            overrides = profiles[active_profile]
            
            # Apply overrides to main sections
            for section, values in overrides.items():
                if section == "timeframes":
                    # For timeframes, we replace the whole dictionary to be safe
                    self.trading[section] = values
                elif section in self.trading and isinstance(self.trading[section], dict) and isinstance(values, dict):
                    # For other dict sections, we perform a shallow merge
                    self.trading[section].update(values)
                else:
                    # For non-dict or new keys, just assign
                    self.trading[section] = values
    
    def _load_json(self, filename: str) -> Dict[str, Any]:
        """Load JSON configuration file."""
        filepath = self._config_dir / filename
        
        if not filepath.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {filepath}\n"
                f"Please create it based on the template."
            )
        
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def get_api_key(self, provider: str) -> str:
        """Get API key for a specific provider."""
        if provider not in self.api_keys:
            raise ValueError(f"Unknown API provider: {provider}")
        
        api_key = self.api_keys[provider].get("api_key", "")
        
        if not api_key or "YOUR_" in api_key:
            raise ValueError(
                f"API key for {provider} not configured.\n"
                f"Please update config/api_keys.json with your actual API key."
            )
        
        return api_key
    
    def get_api_config(self, provider: str) -> Dict[str, Any]:
        """Get full API configuration for a provider."""
        if provider not in self.api_keys:
            raise ValueError(f"Unknown API provider: {provider}")
        
        return self.api_keys[provider]
    
    def get_trading_config(self, key: str = None) -> Any:
        """Get trading configuration value from current merged state."""
        if key is None:
            return self.trading
        
        # Support nested keys like "risk_management.max_risk_per_trade_percent"
        keys = key.split('.')
        value = self.trading
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                raise KeyError(f"Configuration key not found: {key}")
        
        return value
    
    def get_profile_config(self, profile_name: str) -> Dict[str, Any]:
        """
        Returns a complete trading configuration dictionary for a specific profile,
        merged with the base settings, without affecting the global singleton state.
        """
        profiles = self.trading.get("profiles", {})
        if profile_name not in profiles:
            # Fallback to current base if profile not found
            return self.trading.copy()
            
        # Start with a copy of the base settings (as they were loaded from file)
        # Note: self.trading is already potentially merged with active_profile. 
        # To get the PURE base, we'd need to re-load or store it.
        # But for this system, we want to override the CURRENT active state with the new profile.
        
        # Deep copy to avoid side effects
        import copy
        base_cfg = copy.deepcopy(self.trading)
        overrides = profiles[profile_name]
        
        # Apply overrides
        for section, values in overrides.items():
            if section == "timeframes":
                base_cfg[section] = values
            elif section in base_cfg and isinstance(base_cfg[section], dict) and isinstance(values, dict):
                base_cfg[section].update(values)
            else:
                base_cfg[section] = values
                
        return base_cfg
    
    @property
    def pairs(self):
        """Get configured currency pairs."""
        return self.trading.get("pairs", [])
    
    @property
    def timeframes(self):
        """Get configured timeframes."""
        return self.trading.get("timeframes", {})
    
    @property
    def primary_api_provider(self):
        """Get primary API provider."""
        return self.trading.get("api", {}).get("primary_provider", "alpha_vantage")
    
    @property
    def fallback_api_providers(self):
        """Get fallback API providers."""
        return self.trading.get("api", {}).get("fallback_providers", [])


# Global config instance
config = Config()
