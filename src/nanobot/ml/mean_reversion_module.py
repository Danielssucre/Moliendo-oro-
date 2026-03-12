"""
MEAN REVERSION MODULE — Fase 3 del Bot All-Weather
====================================================
Se activa cuando el RegimeDetector declara 'RANGE'.
Opera en mercados laterales usando Bollinger Bands + RSI extremos.
Compra en soporte (oversold) y vende en resistencia (overbought).
"""
import pandas as pd
import numpy as np


class MeanReversionModule:
    """
    Estrategia de reversión a la media para mercados laterales (RANGE).
    Take Profit conservador: 50% del rango detectado.
    """

    # Umbrales de RSI para zonas extremas
    RSI_OVERSOLD     = 30   # Comprar cuando RSI < 30 (sobrevendido)
    RSI_OVERBOUGHT   = 70   # Vender cuando RSI > 70 (sobrecomprado)

    # Bollinger Bands: solo operar cerca de las bandas
    BB_PROXIMITY_PCT = 0.15  # El precio debe estar al 15% dentro de la banda

    # Filtro de ADX: no operar si el ADX repunta (podría romper el rango)
    ADX_MAX_RANGE    = 22.0

    def __init__(self):
        self.last_entry_side = None  # "BUY" o "SELL" para evitar entradas dobles

    def scan_entries(self, df: pd.DataFrame, symbol: str) -> dict:
        """
        df: DataFrame con columnas: close, rsi, adx, bb_upper, bb_lower, bb_mid
        Retorna señal de entrada o None.
        """
        if df is None or len(df) < 20:
            return None

        last = df.iloc[-1]
        close    = float(last.get("close", 0))
        rsi      = float(last.get("rsi", 50))
        adx      = float(last.get("adx", 25))
        bb_upper = float(last.get("bb_upper", close * 1.01))
        bb_lower = float(last.get("bb_lower", close * 0.99))
        bb_mid   = float(last.get("bb_mid", close))

        # Filtro de seguridad: si ADX empieza a subir, el rango está terminando
        if adx > self.ADX_MAX_RANGE:
            return None

        band_range = bb_upper - bb_lower
        if band_range <= 0:
            return None

        # --- Señal COMPRA: precio cerca de banda inferior + RSI sobrevendido ---
        near_lower = (close - bb_lower) / band_range < self.BB_PROXIMITY_PCT
        if near_lower and rsi < self.RSI_OVERSOLD and self.last_entry_side != "BUY":
            tp_price = bb_mid   # TP en la media de Bollinger
            sl_price = bb_lower * 0.998  # SL ligeramente debajo de la banda
            self.last_entry_side = "BUY"
            return {
                "symbol":    symbol,
                "direction": "BUY",
                "tp_target": tp_price,
                "sl_target": sl_price,
                "reason": (
                    f"Mean Reversion BUY: Price near BB lower ({close:.5f}), "
                    f"RSI={rsi:.1f} (oversold), ADX={adx:.1f} (range confirmed)"
                )
            }

        # --- Señal VENTA: precio cerca de banda superior + RSI sobrecomprado ---
        near_upper = (bb_upper - close) / band_range < self.BB_PROXIMITY_PCT
        if near_upper and rsi > self.RSI_OVERBOUGHT and self.last_entry_side != "SELL":
            tp_price = bb_mid
            sl_price = bb_upper * 1.002
            self.last_entry_side = "SELL"
            return {
                "symbol":    symbol,
                "direction": "SELL",
                "tp_target": tp_price,
                "sl_target": sl_price,
                "reason": (
                    f"Mean Reversion SELL: Price near BB upper ({close:.5f}), "
                    f"RSI={rsi:.1f} (overbought), ADX={adx:.1f} (range confirmed)"
                )
            }

        # Sin señal válida
        self.last_entry_side = None
        return None

    def calculate_bollinger(self, df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
        """
        Calcula Bollinger Bands si no vienen precalculadas en el DataFrame.
        Añade columnas: bb_upper, bb_lower, bb_mid
        """
        if "close" not in df.columns:
            return df

        df = df.copy()
        df["bb_mid"]   = df["close"].rolling(period).mean()
        rolling_std    = df["close"].rolling(period).std()
        df["bb_upper"] = df["bb_mid"] + (rolling_std * std_dev)
        df["bb_lower"] = df["bb_mid"] - (rolling_std * std_dev)
        return df
