#!/usr/bin/env python3
"""
API Connectivity Test (The Council of Oracles)
"""
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.utils.config import Config
from src.api.twelvedata import TwelvedataAPI
from src.api.alpha_vantage import AlphaVantageAPI
from src.utils.logger import logger

def test_apis():
    print("--- 🔮 THE COUNCIL OF ORACLES: Connectivity Test ---")
    
    cfg = Config()
    
    # Check Keys (Extract string from dict if needed)
    td_config = cfg.api_keys.get("twelvedata", {})
    td_key = td_config.get("api_key") if isinstance(td_config, dict) else td_config
    
    av_config = cfg.api_keys.get("alpha_vantage", {})
    av_key = av_config.get("api_key") if isinstance(av_config, dict) else av_config
    
    print(f"Twelvedata Key: {'✅ Found' if td_key else '❌ Missing'}")
    print(f"AlphaVantage Key: {'✅ Found' if av_key else '❌ Missing'}")
    
    if td_key:
        try:
            td = TwelvedataAPI(td_key)
            price = td.get_forex_data("GBP/USD", "1h", outputsize=1)
            last_candle = price.iloc[-1]
            print(f"✅ Twelvedata Oracle: GBP/USD Price = {last_candle['close']} at {last_candle.name}")
        except Exception as e:
            print(f"❌ Twelvedata Error: {e}")
            
    if av_key:
        try:
            av = AlphaVantageAPI(av_key)
            # AlphaVantage free tier can be slow/limited
            price = av.get_forex_data("GBPUSD", "60min", outputsize="compact")
            print(f"✅ AlphaVantage Oracle: GBP/USD Price = {price['close'].iloc[-1]}")
        except Exception as e:
            print(f"❌ AlphaVantage Error: {e}")

if __name__ == "__main__":
    test_apis()
