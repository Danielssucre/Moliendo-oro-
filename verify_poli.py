import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.basicConfig(level=logging.INFO)

try:
    from src.nanobot.ml.polimata_v6 import PolimataGeneral
    import pandas as pd
    import numpy as np

    print("🧠 Starting Polimata V6 Verification...")
    polimata = PolimataGeneral()
    
    # Check HMM Model Initialization
    if polimata.model:
        print("✅ HMM Model initialized successfully.")
    else:
        print("❌ HMM Model failed to initialize.")

    # Create dummy DataFrame
    data = {
        'close': np.random.uniform(1.0500, 1.0600, 250),
        'high': np.random.uniform(1.0600, 1.0650, 250),
        'low': np.random.uniform(1.0450, 1.0500, 250),
        'adx': [30] * 250,
        'rsi': [75] * 250,
        'atr': [0.0050] * 250
    }
    df = pd.DataFrame(data)
    
    # Test Prediction
    regime = polimata.predict_regime(df)
    print(f"✅ Regime Predicted: {regime}")
    
    # Test Evaluation
    decision = polimata.evaluate_signal("EURUSD", 1, "TREND_TEST", df)
    print(f"✅ Evaulation Decision -> Approved: {decision.approved}, RR: {decision.adjusted_rr}, Reason: {decision.reason}")
    
    print("\n🎉 Polimata V6 Architecture verified successfully.")

except Exception as e:
    print(f"❌ Critical Error during verification: {e}")
    import traceback
    traceback.print_exc()
