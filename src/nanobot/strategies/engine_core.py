"""
ENGINE (XGBoost) Live Inference Core
========================================
Acts as an elite ML Sniper, evaluating live dataframe rows 
against a pre-trained XGBoost MultiClass Classifier.
"""

import os
import logging
import pandas as pd
import numpy as np

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

logger = logging.getLogger("Nanobot.EngineCore")

class EnginePredictor:
    def __init__(self, models_dir="models"):
        self.models_dir = models_dir
        # Store multiple models mapped by symbol if needed
        self.models = {}
        
        if not XGB_AVAILABLE:
            logger.warning("⚠️ [ENGINE] XGBoost not installed. Engine returning 0.")
            
    def load_model_for_symbol(self, symbol):
        """Lazy load the xgb model for the requested symbol."""
        if symbol in self.models:
            return self.models[symbol]
            
        model_path = os.path.join(self.models_dir, f"engine_v1_{symbol}.xgb")
        if not os.path.exists(model_path):
            # Try loading a generic fallback if specific symbol doesn't exist
            generic_path = os.path.join(self.models_dir, "engine_v1_generic.xgb")
            if os.path.exists(generic_path):
                model_path = generic_path
            else:
                self.models[symbol] = None
                return None
                
        try:
            model = xgb.XGBClassifier()
            model.load_model(model_path)
            self.models[symbol] = model
            logger.info(f"🧠 [ENGINE] Successfully loaded XGBoost for {symbol} ({os.path.basename(model_path)})")
            return model
        except Exception as e:
            logger.error(f"⚠️ [ENGINE] Failed to load model for {symbol}: {e}")
            self.models[symbol] = None
            return None

    def is_ready(self, symbol):
        """Returns True if XGB is available and model is loaded for symbol."""
        if not XGB_AVAILABLE: return False
        return self.load_model_for_symbol(symbol) is not None

    def build_features(self, df):
        """
        Convert raw priced indicators into normalized ML features EXACTLY
        as done in training. The raw indicators (ema_15, adx, etc.) are 
        already added to `df` by `analyze_hybrid_signal` in `run_live.py`.
        """
        try:
            # We only need to process the LAST row for live inference to save CPU,
            # but for safety and vectorized purity, we use pandas directly.
            features = pd.DataFrame(index=[df.index[-1]])
            
            row = df.iloc[-1]
            shift_3 = df.iloc[-4] # .shift(3) equivalent is 4 periods back
            
            features['dist_ema5'] = (row['close'] - row['ema_5']) / row['close']
            features['dist_ema15'] = (row['close'] - row['ema_15']) / row['close']
            features['dist_ema200'] = (row['close'] - row['ema_200']) / row['close']
            
            features['slope_ema15'] = (row['ema_15'] - shift_3['ema_15']) / shift_3['ema_15']
            
            features['rsi'] = row['rsi']
            features['adx'] = row['adx']
            
            features['atr_rel'] = row['atr'] / row['close']
            
            features['bb_width'] = (row['bb_upper'] - row['bb_lower']) / row['bb_mid']
            features['bb_pos'] = (row['close'] - row['bb_lower']) / (row['bb_upper'] - row['bb_lower'] + 1e-9)
            
            # Reorder explicitly to match training if needed
            expected_cols = [
                'dist_ema5', 'dist_ema15', 'dist_ema200', 'slope_ema15',
                'rsi', 'adx', 'atr_rel', 'bb_width', 'bb_pos'
            ]
            
            return features[expected_cols]
            
        except Exception as e:
            logger.error(f"⚠️ [ENGINE] Error building features: {e}")
            return None

    def get_engine_signal(self, df, symbol) -> int:
        """
        Executes the XGBoost multi-classification.
        Returns:
            1: BUY
           -1: SELL
            0: NEUTRAL/WAIT
        """
        if len(df) < 200: return 0
        
        model = self.load_model_for_symbol(symbol)
        if model is None: return 0
        
        X_live = self.build_features(df)
        if X_live is None or X_live.isnull().values.any():
            return 0
            
        try:
            # Multi:softprob returns probability for each class [Sell, Wait, Buy]
            probas = model.predict_proba(X_live)[0]
            
            # Map predictions based purely on mapping used in train: -1=0, 0=1, 1=2
            # probabilities = [Prob(-1), Prob(0), Prob(1)]
            prob_sell = probas[0]
            prob_wait = probas[1]
            prob_buy  = probas[2]
            
            # Tactical Sniper Threshold (We don't take borderline setups)
            CONFIDENCE_THRESHOLD = 0.65
            
            if prob_buy > CONFIDENCE_THRESHOLD:
                return 1
            elif prob_sell > CONFIDENCE_THRESHOLD:
                return -1
            else:
                return 0
                
        except Exception as e:
            logger.error(f"⚠️ [ENGINE] Inference Error: {e}")
            return 0
