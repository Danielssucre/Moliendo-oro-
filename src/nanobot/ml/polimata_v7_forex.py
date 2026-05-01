"""
POLIMATA V7 - FOREX ONLY 🧠
============================
Validador data-driven basado en análisis de datos reales.
Optimizado para Forex usando 70,000+ señales + trading journal.

DATOS REALES ANALIZADOS:
- 89 SELL vs 255 BUY (SELL gana +$33k)
- Hora 15:00 UTC = mejor momento (London/NY overlap)
- AUDUSD, NZDUSD, EURUSD = símbolos winners
- EURNZD = blacklist (0% WR con NEMESIS)
- NEMESIS CHAMPION (RSI >75/<25) = estrategia winners

Versión: 7.0 (FOREX ONLY)
"""

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger("Nanobot.PolimataV7.Forex")


class PolimataDecision:
    def __init__(
        self,
        approved: bool,
        adjusted_rr: float,
        regime: str,
        reason: str,
        extended_rr: float = 0.0,
    ):
        self.approved = approved
        self.adjusted_rr = adjusted_rr
        self.extended_rr = extended_rr
        self.regime = regime
        self.reason = reason


class PolimataV7Forex:
    """
    Polimata V7 - EXCLUSIVO PARA FOREX
    Basado en datos reales de trading journal y operations.jsonl
    """

    VERSION = "7.0.FOREX.ONLY"

    WHITELIST_SYMBOLS = [
        "EURAUD",  # 100% WR con NEMESIS
        "GBPAUD",  # 100% WR con NEMESIS
        "AUDUSD",  # +$18,121 en datos reales
        "NZDUSD",  # +$15,874 en datos reales
        "EURUSD",  # +$15,032 en datos reales
        "GBPJPY",  # +$328 en datos reales
    ]

    BLACKLIST_SYMBOLS = [
        "EURNZD",  # 0% WR con NEMESIS (datos FTMO)
        "NZDJPY",  # 0% WR con NEMESIS (datos FTMO)
        "CHFJPY",  # 0% WR en trading journal
        "USDCHF",  # 0% WR en trading journal
    ]

    OPTIMAL_HOURS = [14, 15, 16]  # UTC - London/NY overlap

    def __init__(self):
        self.version = self.VERSION
        logger.info(f"🧠 [POLIMATA V7 FOREX] Initialized - Version {self.VERSION}")
        logger.info(f"📊 Whitelist: {', '.join(self.WHITELIST_SYMBOLS)}")
        logger.info(f"🚫 Blacklist: {', '.join(self.BLACKLIST_SYMBOLS)}")
        logger.info(f"⏰ Optimal Hours: {self.OPTIMAL_HOURS}")

    def predict_regime(self, df: pd.DataFrame, symbol: str = "UNKNOWN") -> str:
        """Detecta régimen de mercado para Forex."""
        if len(df) < 50:
            return "UNKNOWN"

        adx = df["adx"].iloc[-1] if "adx" in df.columns else 0
        atr = df["atr"].iloc[-1] if "atr" in df.columns else 0.001
        close = df["close"].iloc[-1]
        vol_ratio = atr / close if close > 0 else 0

        if adx < 20 and vol_ratio < 0.002:
            return "CALM_RANGE"
        elif adx >= 25:
            return "TRENDING"
        else:
            return "CHAOTIC"

    def check_symbol(self, symbol: str) -> tuple[bool, str]:
        """
        Verifica si el símbolo está en whitelist o blacklist.
        Returns: (is_allowed, reason)
        """
        sym_up = symbol.upper()

        if sym_up in self.BLACKLIST_SYMBOLS:
            return False, f"BLACKLIST: {sym_up} tiene 0% WR en datos reales."

        if sym_up in self.WHITELIST_SYMBOLS:
            return True, f"WHITELIST: {sym_up} verificado con datos reales."

        return True, f"APPROVED: {sym_up} no está en blacklist."

    def check_hour(self) -> tuple[bool, str]:
        """Verifica si la hora actual es óptima para operar."""
        from datetime import datetime

        current_hour = datetime.utcnow().hour

        if current_hour in self.OPTIMAL_HOURS:
            return True, f"OPTIMAL HOUR: {current_hour}:00 UTC (London/NY overlap)"
        else:
            return (
                False,
                f"OFF-HOURS: {current_hour}:00 UTC no es óptimo (mejor: 14-16 UTC)",
            )

    def evaluate_signal(
        self, symbol: str, signal: int, strategy_tag: str, data: pd.DataFrame
    ) -> PolimataDecision:
        """
        Evalúa señal basándose en:
        1. Symbol whitelist/blacklist
        2. Hour filter (14-16 UTC)
        3. Regime check (CALM_RANGE/TRENDING)
        4. Strategy validation (NEMESIS only)
        """

        # === BARRERA 1: Solo NEMESIS pasa ===
        is_neme = any(k in strategy_tag.upper() for k in ["NEME", "NEMESIS"])
        if not is_neme:
            return PolimataDecision(
                False,
                0.0,
                "FILTERED",
                f"Polimata V7 Forex: Solo NEMESIS autorizado. '{strategy_tag}' bloqueado.",
            )

        # === BARRERA 2: Signal no vacía ===
        if signal == 0:
            return PolimataDecision(False, 0.0, "NONE", "Sin señal.")

        # === BARRERA 3: Symbol whitelist/blacklist ===
        symbol_allowed, symbol_reason = self.check_symbol(symbol)
        if not symbol_allowed:
            logger.info(f"🚫 [POLIMATA V7] {symbol_reason}")
            return PolimataDecision(False, 0.0, "BLACKLIST", symbol_reason)

        # === BARRERA 4: Hour filter ===
        hour_allowed, hour_reason = self.check_hour()
        if not hour_allowed:
            logger.info(f"⏰ [POLIMATA V7] {hour_reason}")
            return PolimataDecision(False, 0.0, "OFF_HOURS", hour_reason)

        # === Contexto de mercado ===
        if len(data) < 50:
            return PolimataDecision(
                True,
                2.5,
                "UNKNOWN",
                "Contexto insuficiente: paso por defecto.",
                extended_rr=5.0,
            )

        regime = self.predict_regime(data, symbol)
        rsi = data["rsi"].iloc[-1] if "rsi" in data.columns else 50
        adx = data["adx"].iloc[-1] if "adx" in data.columns else 20

        # === BARRERA 5: Regime check ===
        if regime == "CHAOTIC":
            return PolimataDecision(
                False, 0.0, regime, "Caos detectado: mercado no óptimo para Forex."
            )

        # === AUTORIZACIÓN NEME PRIME (Forex) ===
        if regime == "CALM_RANGE":
            logger.info(
                f"✅ [POLIMATA V7] CALM_RANGE para {symbol} | RSI={rsi:.0f} | ADX={adx:.0f}"
            )
            return PolimataDecision(
                True,
                2.5,
                regime,
                f"✅ CALM_RANGE: Entorno ideal para NEME. RR 1:2.5 | {symbol_reason}",
                extended_rr=4.0,
            )

        # TRENDING: CHAMPION busca agotamiento
        if regime == "TRENDING":
            is_exhausted = (rsi > 75 and signal == -1) or (rsi < 25 and signal == 1)
            if is_exhausted:
                logger.info(
                    f"✅ [POLIMATA V7] TRENDING exhausto para {symbol} | RSI={rsi:.0f}"
                )
                return PolimataDecision(
                    True,
                    2.5,
                    regime,
                    f"✅ TRENDING exhausto: Reversión NEME autorizada. RR 1:2.5 | {symbol_reason}",
                    extended_rr=5.0,
                )

            is_relaxed = (rsi > 60 and signal == -1) or (rsi < 40 and signal == 1)
            if is_relaxed:
                return PolimataDecision(
                    True,
                    1.5,
                    regime,
                    f"⚠️ TRENDING parcial (RSI={rsi:.0f}): NEME modo conservador. RR 1:1.5",
                )

            return PolimataDecision(
                False,
                0.0,
                regime,
                f"❌ TRENDING sin agotamiento (RSI={rsi:.0f}): NEME rechazado.",
            )

        return PolimataDecision(
            True,
            1.5,
            "UNKNOWN",
            "Régimen desconocido: NEME aprobado con RR conservador.",
        )


def create_polimata_v7_forex() -> PolimataV7Forex:
    """Factory function para crear Polimata V7 Forex."""
    return PolimataV7Forex()
