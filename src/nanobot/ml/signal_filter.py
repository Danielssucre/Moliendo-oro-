"""
SIGNAL FILTER ML
================
Usa Random Forest entrenado para filtrar señales malas.
Solo pasa señales que el modelo predice como "buenas" (>=2R potential).
"""

import joblib
import os
import numpy as np
import logging

logger = logging.getLogger("Nanobot.SignalFilter")

REGIME_MAP = {"CALM_RANGE": 0, "TRENDING": 1, "CHAOTIC": 2}


class SignalFilterML:
    VERSION = "1.0.RF"

    def __init__(self, model_path=None):
        if model_path is None:
            base_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            )
            model_path = os.path.join(
                base_dir, "models", "signal_filter", "rf_signal_filter.joblib"
            )

        self.model = None
        self.loaded = False
        self.model_path = model_path
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                self.loaded = True
                logger.info(f"✅ Signal Filter ML loaded: {self.model_path}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load Signal Filter: {e}")
        else:
            logger.warning(f"⚠️ Signal Filter model not found: {self.model_path}")

    def predict(
        self,
        hour,
        m5_adx,
        m5_rsi,
        m5_dist_200,
        h1_adx,
        h1_rsi,
        h1_dist_200,
        h1_trend,
        vol_ratio,
        regime,
    ) -> tuple:
        """
        Predice si una señal debe ser tomada o saltada.

        Args:
            hour: Hour of trade (0-23)
            m5_adx, m5_rsi, m5_dist_200: M5 timeframe indicators
            h1_adx, h1_rsi, h1_dist_200, h1_trend: H1 timeframe indicators
            vol_ratio: Volatility ratio
            regime: "CALM_RANGE", "TRENDING", or "CHAOTIC"

        Returns:
            (should_take: bool, confidence: float, reason: str)
        """
        if not self.loaded or self.model is None:
            return True, 0.5, "ML model not loaded - passing signal"

        try:
            regime_encoded = REGIME_MAP.get(regime, 0)

            features = np.array(
                [
                    [
                        hour,
                        m5_adx,
                        m5_rsi,
                        m5_dist_200,
                        h1_adx,
                        h1_rsi,
                        h1_dist_200,
                        h1_trend,
                        vol_ratio,
                        regime_encoded,
                    ]
                ]
            )

            prob = self.model.predict_proba(features)[0]
            confidence = prob[1]
            prediction = self.model.predict(features)[0]

            should_take = bool(prediction)

            if confidence < 0.35:
                should_take = True
                reason = f"ML: LOW_CONF (conf={confidence:.2%}) - letting pass"
            else:
                reason = (
                    f"ML: {'TAKE' if should_take else 'SKIP'} (conf={confidence:.2%})"
                )

            return should_take, confidence, reason

        except Exception as e:
            logger.error(f"Signal Filter prediction error: {e}")
            return True, 0.5, "ML error - passing signal"

    def is_regime_safe(self, regime: str) -> bool:
        """Verifica si el régimen es tradable."""
        return regime in ["CALM_RANGE", "TRENDING"]


def create_signal_filter() -> SignalFilterML:
    """Factory function."""
    return SignalFilterML()
