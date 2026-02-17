import os
import joblib
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from ..utils.logger import logger
from ..utils.config import config

class StopHuntModel:
    """
    ML Filter to detect potential Stop Hunts.
    Uses Random Forest to classify if a setup is a "Trap".
    """
    
    def __init__(self, model_path: str = None):
        self.model_path = model_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "models", "stop_hunt_rf_calibrated.joblib"
        )
        self.model = None
        self.is_trained = False
        self._load_model()

    def _load_model(self):
        """Load the pre-trained model if it exists."""
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                self.is_trained = True
                logger.info(f"✅ Stop Hunt ML Model loaded from {self.model_path}")
            except Exception as e:
                logger.error(f"Error loading ML model: {e}")

    def extract_features(self, df: pd.DataFrame, current_price: float, indicators: Dict) -> Dict:
        """
        Extract features specifically related to stop hunts.
        """
        if df is None or len(df) < 5:
            return {}

        last_candles = df.tail(5)
        
        # 1. Wick-to-Body Ratio (Exhaustion/Trap detection)
        # Ratio of total wicks vs real bodies in last 3 candles
        wick_size = (last_candles['high'] - last_candles[['open', 'close']].max(axis=1)).sum() + \
                    (last_candles[['open', 'close']].min(axis=1) - last_candles['low']).sum()
        body_size = (last_candles['open'] - last_candles['close']).abs().sum()
        wick_ratio = wick_size / (body_size + 1e-6)

        # 2. Volatility Spike (ATR acceleration)
        atr = indicators.get('atr', 0)
        atr_avg = df['high'].sub(df['low']).rolling(20).mean().iloc[-1]
        volatility_surge = atr / (atr_avg + 1e-6)

        # 3. Distance to liquidity (nearest S/R) - normalized by ATR
        # (This will be injected from TradingAgent)
        
        # 4. Successive Same-Color Candles
        # Aggressive moves into S/R often precede hunts
        last_body_positive = (last_candles['close'] > last_candles['open']).astype(int)
        successive_move = last_body_positive.sum() / 5.0 # Proportion of bullish candles

        # 5. INSTITUTIONAL FEATURES
        vwap = indicators.get('vwap', current_price)
        vwap_dist = (current_price - vwap) / (atr + 1e-6)
        
        supertrend_dir = indicators.get('supertrend_dir', 0)
        atr_norm = indicators.get('atr_norm', 0)

        return {
            'wick_ratio': wick_ratio,
            'volatility_surge': volatility_surge,
            'successive_move': successive_move,
            'rsi': indicators.get('rsi', 50),
            'adx': indicators.get('adx', 0)
        }

    def predict_risk(self, features: Dict) -> float:
        """
        Returns a risk score 0-1 (1 = High Stop Hunt Risk).
        If model not trained, returns a conservative baseline.
        """
        if not self.is_trained or not features:
            return 0.2 # Baseline risk

        try:
            # Match training features exactly
            model_features = ['wick_ratio', 'volatility_surge', 'successive_move', 'rsi', 'adx']
            X = pd.DataFrame([[features.get(f, 0) for f in model_features]], columns=model_features)
            prob = self.model.predict_proba(X)[0][1] # Probability of Class 1 (Stop Hunt)
            return float(prob)
        except Exception as e:
            logger.debug(f"Prediction error: {e}")
            return 0.3

    def save_model(self, model, path: str = None):
        """Save a trained model."""
        target_path = path or self.model_path
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        joblib.dump(model, target_path)
        self.model = model
        self.is_trained = True
        logger.info(f"🚀 Model saved to {target_path}")
