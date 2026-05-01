"""
CRYPTO LAB: Sistema de Trading para Criptomonedas
===================================================
Motor especializado para BTCUSD, ETHUSD, SOLUSD en MT5.

Estrategias base (en orden de prioridad):
1. SQUEEZE MOMENTUM: Bollinger Bands + ATR squeeze breakout
2. REGIME TREND: EMA crossover con confirmación de tendencia
3. VOLATILITY BREAKOUT: High ATR + volumen + momentum
4. VOLUME PROFILE: Oscilación entre support/resistance con volumen
5. DEEP FLIP: Reversión en extremos con confirmación

ANTITHESIS = INVERSIÓN de señal base (como NEMESIS en Forex)
- Si base dice BUY → ANTITHESIS dice SELL
- Si base dice SELL → ANTITHESIS dice BUY

Parámetros Crypto (vs Forex):
- RR: 3.0 (mayor por volatilidad)
- SL: ATR × 2.0
- TP: ATR × 6.0
- Timeframes: M15 / H1 / H4
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict


class CryptoLab:
    """
    Motor de señales CRYPTO puras.
    
    Genera señal base con estrategias SQUEEZE/REGIME/BREAKOUT.
    ANTITHESIS invierte la señal base.
    """

    CRYPTO_PAIRS = ["BTCUSD", "ETHUSD", "SOLUSD"]
    
    def __init__(self):
        self._last_squeeze_state = None
        self._last_cross = 0
        
    def _detect_squeeze(self, df: pd.DataFrame) -> Tuple[bool, float]:
        """
        Detecta squeeze de Bollinger Bands + ATR.
        Returns: (is_squeezing, squeeze_strength 0-1)
        """
        if len(df) < 20:
            return False, 0.0
            
        if "bb_upper" not in df.columns or "bb_lower" not in df.columns:
            return False, 0.0
            
        if "atr" not in df.columns:
            return False, 0.0
            
        bb_width = (df["bb_upper"].iloc[-1] - df["bb_lower"].iloc[-1]) / df["close"].iloc[-1]
        bb_width_prev = (df["bb_upper"].iloc[-2] - df["bb_lower"].iloc[-2]) / df["close"].iloc[-2]
        bb_width_avg = bb_width / df["close"].ewm(span=20).mean().iloc[-1] if "close" in df.columns else bb_width
        
        atr_current = df["atr"].iloc[-1] if "atr" in df.columns else 0.01
        atr_avg = df["atr"].rolling(20).mean().iloc[-1] if "atr" in df.columns else atr_current
        
        squeeze_ratio = atr_current / atr_avg if atr_avg > 0 else 1.0
        
        is_squeezing = bb_width < bb_width_prev * 0.9 and squeeze_ratio < 0.8
        
        strength = max(0, min(1, (1.0 - squeeze_ratio)))
        
        return is_squeezing, strength

    def _detect_ema_cross(self, df: pd.DataFrame, fast: int = 9, slow: int = 21) -> int:
        """Detecta crossover de EMA. Returns: 1=bullish, -1=bearish, 0=no cross"""
        if len(df) < slow + 2:
            return 0
            
        ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
        
        ema_f = ema_fast.iloc[-1]
        ema_s = ema_slow.iloc[-1]
        prev_f = ema_fast.iloc[-2]
        prev_s = ema_slow.iloc[-2]
        
        cross = 0
        if prev_f <= prev_s and ema_f > ema_s:
            cross = 1
        elif prev_f >= prev_s and ema_f < ema_s:
            cross = -1
            
        self._last_cross = cross
        return cross

    def _get_regime(self, df: pd.DataFrame) -> str:
        """Determina el régimen de mercado: TREND, RANGE, VOLATILE"""
        if len(df) < 50:
            return "RANGE"
            
        adx = df["adx"].iloc[-1] if "adx" in df.columns else 20
        rsi = df["rsi"].iloc[-1] if "rsi" in df.columns else 50
        atr_pct = (df["atr"].iloc[-1] / df["close"].iloc[-1]) if "atr" in df.columns else 0.02
        
        if adx > 25 and atr_pct > 0.01:
            return "TREND"
        elif adx < 15 and atr_pct < 0.005:
            return "RANGE"
        elif atr_pct > 0.03:
            return "VOLATILE"
        else:
            return "RANGE"

    def get_base_signal_with_strategy(self, df: pd.DataFrame) -> Tuple[int, str, Dict]:
        """
        Genera señal base CON el nombre de la estrategia y metadata.
        Returns: (signal, strategy_name, metadata)
        """
        if len(df) < 50:
            return 0, "NONE", {}
            
        sig = 0
        strategy = "NONE"
        metadata = {
            "regime": self._get_regime(df),
            "squeeze": False,
            "atr_pct": 0,
            "volume_ratio": 1.0,
            "confidence": 0.0
        }
        
        rsi = df["rsi"].iloc[-1] if "rsi" in df.columns else 50
        prev_rsi = df["rsi"].iloc[-2] if "rsi" in df.columns else 50
        adx = df["adx"].iloc[-1] if "adx" in df.columns else 20
        close = df["close"].iloc[-1] if "close" in df.columns else 0
        
        ema_200 = df["ema_200"].iloc[-1] if "ema_200" in df.columns else close
        atr = df["atr"].iloc[-1] if "atr" in df.columns else close * 0.02
        atr_pct = atr / close if close > 0 else 0.02
        metadata["atr_pct"] = atr_pct
        
        if "volume" in df.columns and len(df) > 20:
            vol_avg = df["volume"].rolling(20).mean().iloc[-1]
            vol_current = df["volume"].iloc[-1]
            metadata["volume_ratio"] = vol_current / vol_avg if vol_avg > 0 else 1.0
        
        last_cross = self._detect_ema_cross(df)
        is_squeezing, squeeze_strength = self._detect_squeeze(df)
        metadata["squeeze"] = is_squeezing
        
        if sig == 0 and is_squeezing and squeeze_strength > 0.5:
            if adx > 20:
                if rsi < 30 and close < ema_200:
                    sig = 1
                    strategy = "SQUEEZE_LONG"
                    metadata["confidence"] = 0.7 + squeeze_strength * 0.3
                elif rsi > 70 and close > ema_200:
                    sig = -1
                    strategy = "SQUEEZE_SHORT"
                    metadata["confidence"] = 0.7 + squeeze_strength * 0.3
            elif adx < 15:
                if rsi < 35:
                    sig = 1
                    strategy = "SQUEEZE_LONG"
                    metadata["confidence"] = 0.6 + squeeze_strength * 0.2
                elif rsi > 65:
                    sig = -1
                    strategy = "SQUEEZE_SHORT"
                    metadata["confidence"] = 0.6 + squeeze_strength * 0.2

        if sig == 0 and last_cross != 0 and adx > 18:
            ema_50 = df["close"].ewm(span=50, adjust=False).mean().iloc[-1] if len(df) >= 50 else close
            if last_cross == 1 and close > ema_200:
                sig = 1
                strategy = "REGIME_TREND"
                metadata["confidence"] = 0.75
            elif last_cross == -1 and close < ema_200:
                sig = -1
                strategy = "REGIME_TREND"
                metadata["confidence"] = 0.75

        if sig == 0 and atr_pct > 0.015:
            if metadata["volume_ratio"] > 1.5:
                if rsi < 40 and adx > 20:
                    sig = 1
                    strategy = "VOLATILITY_LONG"
                    metadata["confidence"] = 0.65
                elif rsi > 60 and adx > 20:
                    sig = -1
                    strategy = "VOLATILITY_SHORT"
                    metadata["confidence"] = 0.65

        if sig == 0 and adx < 20:
            if rsi < 30:
                sig = 1
                strategy = "DEEP_LONG"
                metadata["confidence"] = 0.6
            elif rsi > 70:
                sig = -1
                strategy = "DEEP_SHORT"
                metadata["confidence"] = 0.6

        if sig == 0:
            if "bb_lower" in df.columns and "bb_upper" in df.columns:
                bb_lower = df["bb_lower"].iloc[-1]
                bb_upper = df["bb_upper"].iloc[-1]
                if close < bb_lower and rsi < 35:
                    sig = 1
                    strategy = "BB_REBOUND_LONG"
                    metadata["confidence"] = 0.65
                elif close > bb_upper and rsi > 65:
                    sig = -1
                    strategy = "BB_REBOUND_SHORT"
                    metadata["confidence"] = 0.65

        return sig, strategy, metadata

    def get_base_signal(self, df: pd.DataFrame) -> int:
        """Alias para get_base_signal_with_strategy()[0]"""
        sig, _, _ = self.get_base_signal_with_strategy(df)
        return sig

    def get_antithesis_signal(self, df: pd.DataFrame) -> int:
        """
        ANTITHESIS = INVERSIÓN de señal base (como NEMESIS en Forex).
        Returns: 1=BUY, -1=SELL, 0=No signal
        """
        if len(df) < 50:
            return 0
            
        base_sig, _, _ = self.get_base_signal_with_strategy(df)
        
        if base_sig != 0:
            return -base_sig
            
        return 0

    def get_antithesis_signal_with_strategy(self, df: pd.DataFrame) -> Tuple[int, str, Dict]:
        """
        ANTITHESIS = INVERSIÓN de señal base CON nombre de estrategia.
        Returns: (signal, strategy_name, metadata)
        """
        if len(df) < 50:
            return 0, "NONE", {}
            
        base_sig, base_strategy, base_meta = self.get_base_signal_with_strategy(df)
        
        if base_sig != 0:
            anti_strategy = f"ANTI_{base_strategy}"
            return -base_sig, anti_strategy, base_meta
            
        return 0, "NONE", {}

    def get_signal_with_mode(self, df: pd.DataFrame, mode: str = "THESIS") -> Tuple[int, str, Dict]:
        """
       获取信号，支持 THESIS（原始）或 ANTITHESIS（反转）模式。
        
        Args:
            df: Pandas DataFrame with OHLCV data and indicators
            mode: "THESIS" (original signal) or "ANTITHESIS" (inverted signal)
            
        Returns:
            Tuple of (signal, strategy_name, metadata)
        """
        if mode.upper() == "ANTITHESIS":
            return self.get_antithesis_signal_with_strategy(df)
        else:
            return self.get_base_signal_with_strategy(df)

    def get_recommended_rr(self, df: pd.DataFrame) -> float:
        """Get recommended Risk:Reward based on regime and volatility"""
        regime = self._get_regime(df)
        atr_pct = (df["atr"].iloc[-1] / df["close"].iloc[-1]) if len(df) > 0 and "atr" in df.columns and "close" in df.columns else 0.02
        
        if regime == "VOLATILE":
            return 5.0
        elif regime == "TREND":
            return 3.0
        else:
            return 4.0