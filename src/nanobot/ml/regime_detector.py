"""
RÉGIMEN DETECTOR — Fase 1 del Bot All-Weather
==============================================
Clasifica el estado actual del mercado en uno de 4 regímenes:
    - TREND:  Tendencia clara, ADX alto. → Activa HIVE V5
    - RANGE:  Mercado lateral, ADX bajo.  → Activa Mean Reversion
    - CRISIS: Pánico global, Oro/JPY acelerados. → Activa Safe Haven
    - SPIKE:  Volatilidad extrema (noticia). → Cooldown forzado
"""
import numpy as np
import pandas as pd


class RegimeDetector:
    """
    Detecta el régimen de mercado basándose en múltiples indicadores.
    Es el 'director de orquesta' del sistema multilayer.
    """

    # --- Umbrales configurables ---
    ADX_TREND_THRESHOLD  = 25.0   # ADX ≥ 25 → tendencia definida
    ADX_RANGE_THRESHOLD  = 20.0   # ADX ≤ 20 → mercado lateral
    ATR_SPIKE_MULTIPLIER = 2.0    # ATR actual > 2x media → spike de noticias
    GOLD_CRISIS_PCT      = 1.5    # Oro sube/baja >1.5% en 30 min → crisis
    GOLD_CRISIS_WINDOW   = 6      # Ventana de 6 velas de 5 min = 30 minutos

    def __init__(self):
        self.last_regime   = "TREND"   # Último régimen detectado
        self.regime_history = []        # Historial para suavizado

    # ------------------------------------------------------------------
    # MÉTODO PRINCIPAL
    # ------------------------------------------------------------------
    def detect(self, df: pd.DataFrame, gold_df: pd.DataFrame = None) -> str:
        """
        df       → DataFrame del par principal con columnas: adx, atr, close
        gold_df  → DataFrame de XAUUSD (misma temporalidad). Puede ser None.

        Retorna: 'TREND' | 'RANGE' | 'CRISIS' | 'SPIKE'
        """
        try:
            regime = self._evaluate(df, gold_df)
        except Exception as e:
            print(f"⚠️ RegimeDetector error: {e}. Defaulting to TREND.")
            regime = "TREND"

        # Suavizado: solo cambia régimen si lo confirma 2 ciclos seguidos
        self.regime_history.append(regime)
        if len(self.regime_history) > 3:
            self.regime_history.pop(0)

        confirmed_regime = self._confirm_regime()
        self.last_regime  = confirmed_regime
        return confirmed_regime

    # ------------------------------------------------------------------
    # LÓGICA DE EVALUACIÓN INTERNA
    # ------------------------------------------------------------------
    def _evaluate(self, df: pd.DataFrame, gold_df: pd.DataFrame) -> str:

        # 1. Chequeo de CRISIS: tiene prioridad máxima
        if gold_df is not None and len(gold_df) >= self.GOLD_CRISIS_WINDOW:
            gold_move = self._gold_crisis_move(gold_df)
            if abs(gold_move) >= self.GOLD_CRISIS_PCT:
                print(f"🚨 RÉGIMEN: CRISIS detectada (Oro {gold_move:+.2f}% en 30 min)")
                return "CRISIS"

        # Necesitamos al menos la última fila
        if df is None or len(df) < 2:
            return "TREND"

        last = df.iloc[-1]
        adx  = float(last.get("adx", 0))
        atr  = float(last.get("atr", 0))

        # 2. Chequeo de SPIKE: ATR explota (noticia)
        avg_atr = float(df["atr"].tail(20).mean()) if "atr" in df.columns else 0
        if avg_atr > 0 and atr > (avg_atr * self.ATR_SPIKE_MULTIPLIER):
            pct = (atr / avg_atr) * 100
            print(f"💥 RÉGIMEN: SPIKE (ATR {pct:.0f}% sobre media)")
            return "SPIKE"

        # 3. Evaluación de TREND vs RANGE por ADX
        if adx >= self.ADX_TREND_THRESHOLD:
            print(f"📈 RÉGIMEN: TREND (ADX={adx:.1f})")
            return "TREND"
        elif adx <= self.ADX_RANGE_THRESHOLD:
            print(f"↔️ RÉGIMEN: RANGE (ADX={adx:.1f})")
            return "RANGE"

        # 4. Zona gris (ADX entre 20-25): mantener último régimen conocido
        print(f"🔘 RÉGIMEN: Gris (ADX={adx:.1f}). Manteniendo: {self.last_regime}")
        return self.last_regime

    def _gold_crisis_move(self, gold_df: pd.DataFrame) -> float:
        """Calcula el % de movimiento del Oro en la ventana de Crisis."""
        closes = gold_df["close"].tail(self.GOLD_CRISIS_WINDOW)
        if len(closes) < 2:
            return 0.0
        pct_change = ((closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0]) * 100
        return round(pct_change, 3)

    def _confirm_regime(self) -> str:
        """
        Suavizado de régimen: solo confirma si los últimos 2 de 3 registros coinciden.
        Evita cambios erráticos entre regímenes en mercados límites.
        """
        if len(self.regime_history) < 2:
            return self.regime_history[-1]

        last_two = self.regime_history[-2:]
        if last_two[0] == last_two[1]:
            return last_two[1]

        # Si no hay consenso, usar el último detectado directamente
        return self.regime_history[-1]
