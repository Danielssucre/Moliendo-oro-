
import sys
import os
import numpy as np
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nanobot.ml.risk_oracle import AsymmetricRiskOracle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VERIFY_SPECIALIST")

def verify():
    print("\n" + "="*60)
    print("🧪 VERIFICACIÓN DE ESPECIALISTA RL: BTCUSD")
    print("="*60)
    
    # Init Oracle
    # Pass a dummy path for global model just to test fallback if needed
    oracle = AsymmetricRiskOracle(rl_model_path="models/risk_oracle_rl_v3_balanced.zip")
    
    # Test symbols
    test_symbols = ["EURUSD", "BTCUSD", "GBPJPY", "USDJPY"]
    
    for sym in test_symbols:
        print(f"\n🔍 Testing Symbol: {sym}")
        
        # Mock features
        # [prob, adx, rsi, vol, dd]
        prob = 0.85
        adx = 26.0
        rsi = 65.0
        vol = 4.0
        dd = 0.01
        
        mult = oracle.calculate_sizing_multiplier(
            probability=prob,
            adx=adx,
            rsi=rsi,
            vol=vol,
            current_dd=dd,
            symbol=sym
        )
        
        # Check if BTCUSD model was loaded (should see a log entry from RiskOracle)
        print(f"✅ Multiplier for {sym}: {mult}x")
    
    print("\n" + "="*60)
    print("✅ VERIFICACIÓN COMPLETADA")
    print("="*60 + "\n")

if __name__ == "__main__":
    verify()
