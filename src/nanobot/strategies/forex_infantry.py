"""
FOREX INFANTRY ⚔️: NEMESIS System
==================================
Motor de señales FOREX basado en NEMESIS 4898079.

Estrategias base (en orden de prioridad):
1. ZENITH: EMA 9/15 crossover + ADX > 25 + RSI confirmation
2. HIVE V6: EMA 9/15 crossover + ADX > 18 + RSI relaxed
3. ORION: Pullback Sniper (RSI crossing 45/55)
4. FRACTAL ALPHA: Fast EMA 5/13 momentum
5. FRACTAL BETA: Mean Reversion (RSI < 30 / > 70 + low ADX)
6. FRACTAL GAMMA: Chaos Breakout (L3 High/Low)
7. FRACTAL DELTA: Liquidity Sweep detection
8. FRACTAL EPSILON: Institutional MR (RSI + Bollinger Bands)

NEMESIS = INVERSIÓN de señal base (Antithesis)
- Si base dice BUY → NEMESIS dice SELL
- Si base dice SELL → NEMESIS dice BUY

Histórico FTMO:
- NEMESIS: 61.7% Win Rate ✅

Parámetros:
- RR: 1.5 (fijo)
- SL: ATR × 1.5
- TP: ATR × 2.25
"""

import pandas as pd
from typing import Tuple


class ForexInfantry:
    """
    Motor NEMESIS puro.

    Genera señal base con estrategias HIVE/FRACTAL.
    NEMESIS invierte la señal base.
    """

    def __init__(self):
        self._last_ema_cross = 0

    def _detect_ema_cross(self, df: pd.DataFrame) -> int:
        """Detecta crossover de EMA 9/15. Returns: 1=bullish, -1=bearish, 0=no cross"""
        if len(df) < 2:
            return 0

        ema_9 = df["ema_9"].iloc[-1] if "ema_9" in df.columns else 0
        ema_15 = df["ema_15"].iloc[-1] if "ema_15" in df.columns else 0
        prev_ema_9 = df["ema_9"].iloc[-2] if "ema_9" in df.columns else 0
        prev_ema_15 = df["ema_15"].iloc[-2] if "ema_15" in df.columns else 0

        if ema_9 == 0 or prev_ema_9 == 0:
            return 0

        cross = 0
        if prev_ema_9 <= prev_ema_15 and ema_9 > ema_15:
            cross = 1
        elif prev_ema_9 >= prev_ema_15 and ema_9 < ema_15:
            cross = -1

        self._last_ema_cross = cross
        return cross

    def get_base_signal_with_strategy(self, df: pd.DataFrame) -> Tuple[int, str]:
        """
        Genera señal base CON el nombre de la estrategia.
        Returns: (signal, strategy_name) donde signal=1(BUY), -1(SELL), 0(Nada)
        """
        if len(df) < 20:
            return 0, "NONE"

        sig = 0
        strategy = "NONE"

        rsi = df["rsi"].iloc[-1] if "rsi" in df.columns else 50
        prev_rsi = df["rsi"].iloc[-2] if "rsi" in df.columns else 50
        adx = df["adx"].iloc[-1] if "adx" in df.columns else 0

        ema_9 = df["ema_9"].iloc[-1] if "ema_9" in df.columns else 0
        ema_15 = df["ema_15"].iloc[-1] if "ema_15" in df.columns else 0
        ema_200 = df["ema_200"].iloc[-1] if "ema_200" in df.columns else 0
        close = df["close"].iloc[-1] if "close" in df.columns else 0

        last_cross = self._detect_ema_cross(df)

        # ZENITH: EMA crossover + ADX > 25 + RSI confirmation
        if last_cross != 0 and adx > 25:
            if last_cross == 1 and close > ema_200 and rsi > 50:
                sig = 1
                strategy = "ZENITH"
            elif last_cross == -1 and close < ema_200 and rsi < 50:
                sig = -1
                strategy = "ZENITH"

        # HIVE V6: EMA crossover + ADX > 18 + RSI relaxed
        if sig == 0 and last_cross != 0 and adx > 18:
            if last_cross == 1 and close > ema_200 and rsi > 45:
                sig = 1
                strategy = "HIVE_V6"
            elif last_cross == -1 and close < ema_200 and rsi < 55:
                sig = -1
                strategy = "HIVE_V6"

        # ORION: Pullback Sniper
        if sig == 0 and adx > 20:
            if ema_9 > ema_15 and close > ema_200:
                if prev_rsi < 45 and rsi >= 45:
                    sig = 1
                    strategy = "ORION"
            elif ema_9 < ema_15 and close < ema_200:
                if prev_rsi > 55 and rsi <= 55:
                    sig = -1
                    strategy = "ORION"

        # FRACTAL ALPHA: Fast EMA 5/13
        if sig == 0:
            df_copy = df.copy()
            df_copy["ema_5"] = df_copy["close"].ewm(span=5, adjust=False).mean()
            df_copy["ema_13"] = df_copy["close"].ewm(span=13, adjust=False).mean()
            c5 = df_copy["ema_5"].iloc[-2]
            n5 = df_copy["ema_5"].iloc[-1]
            c13 = df_copy["ema_13"].iloc[-2]
            n13 = df_copy["ema_13"].iloc[-1]

            if c5 <= c13 and n5 > n13 and rsi > 50:
                sig = 1
                strategy = "FRACTAL_ALPHA"
            elif c5 >= c13 and n5 < n13 and rsi < 50:
                sig = -1
                strategy = "FRACTAL_ALPHA"

        # FRACTAL BETA: Mean Reversion (RSI < 30 / > 70 + low ADX)
        if sig == 0 and adx < 20:
            if rsi < 30:
                sig = 1
                strategy = "FRACTAL_BETA"
            elif rsi > 70:
                sig = -1
                strategy = "FRACTAL_BETA"

        # FRACTAL GAMMA: Chaos Breakout (L3 H/L)
        if sig == 0 and len(df) >= 4:
            l3 = df.iloc[-4:-1]
            if "high" in df.columns and "low" in df.columns:
                if close > l3["high"].max():
                    sig = 1
                    strategy = "FRACTAL_GAMMA"
                elif close < l3["low"].min():
                    sig = -1
                    strategy = "FRACTAL_GAMMA"

        # FRACTAL DELTA: Liquidity Sweep
        if (
            sig == 0
            and "rolling_high_24" in df.columns
            and "rolling_low_24" in df.columns
        ):
            prev_h = df["rolling_high_24"].iloc[-2]
            prev_l = df["rolling_low_24"].iloc[-2]
            if "high" in df.columns and "low" in df.columns:
                if df["low"].iloc[-1] < prev_l and close > prev_l and rsi < 40:
                    sig = 1
                    strategy = "FRACTAL_DELTA"
                elif df["high"].iloc[-1] > prev_h and close < prev_h and rsi > 60:
                    sig = -1
                    strategy = "FRACTAL_DELTA"

        # FRACTAL EPSILON: Institutional MR (RSI + Bollinger)
        if sig == 0 and "bb_lower" in df.columns and "bb_upper" in df.columns:
            bb_lower = df["bb_lower"].iloc[-1] if "bb_lower" in df.columns else 0
            bb_upper = df["bb_upper"].iloc[-1] if "bb_upper" in df.columns else 0
            if rsi < 30 and close < bb_lower:
                sig = 1
                strategy = "FRACTAL_EPSILON"
            elif rsi > 70 and close > bb_upper:
                sig = -1
                strategy = "FRACTAL_EPSILON"

        return sig, strategy

    def get_base_signal(self, df: pd.DataFrame) -> int:
        """Alias para get_base_signal_with_strategy()[0]"""
        sig, _ = self.get_base_signal_with_strategy(df)
        return sig

    def get_nemesis_signal(self, df: pd.DataFrame) -> int:
        """
        NEMESIS = INVERSIÓN de señal base.
        Returns: 1=BUY, -1=SELL, 0=No signal
        """
        if len(df) < 20:
            return 0

        base_sig, _ = self.get_base_signal_with_strategy(df)

        if base_sig != 0:
            return -base_sig  # INVERTIR

        return 0

    def get_nemesis_signal_with_strategy(self, df: pd.DataFrame) -> Tuple[int, str]:
        """
        NEMESIS = INVERSIÓN de señal base CON nombre de estrategia.
        Returns: (signal, strategy_name) donde strategy = "NEME_[BASE_STRATEGY]"
        """
        if len(df) < 20:
            return 0, "NONE"

        base_sig, base_strategy = self.get_base_signal_with_strategy(df)

        if base_sig != 0:
            neme_strategy = f"NEME_{base_strategy}"
            return -base_sig, neme_strategy

        return 0, "NONE"

    def get_champion_signal(self, df: pd.DataFrame) -> int:
        """Alias para get_base_signal()"""
        return self.get_base_signal(df)

    def get_nemesis_reversion_signal(self, df: pd.DataFrame) -> int:
        """Alias for get_nemesis_signal()"""
        return self.get_nemesis_signal(df)
