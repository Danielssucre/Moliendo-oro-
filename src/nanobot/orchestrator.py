"""
BOT ORCHESTRATOR — Fase 4+5 del Bot All-Weather
================================================
Director de orquesta del sistema multilayer.
En cada ciclo evalúa el régimen y activa el módulo correcto:
    TREND  → HIVE V5 (motor técnico actual)
    RANGE  → MeanReversionModule
    CRISIS → SafeHavenModule
    SPIKE  → Cooldown de 30 minutos (cero exposición nueva)

    + RL Portfolio Allocator: pondera el capital entre módulos en cada ciclo.
"""
import logging
from datetime import datetime, timezone

from src.nanobot.ml.regime_detector      import RegimeDetector
from src.nanobot.ml.safe_haven_module    import SafeHavenModule
from src.nanobot.ml.mean_reversion_module import MeanReversionModule

try:
    from src.nanobot.ml.rl_portfolio_allocator import RLPortfolioAllocator
    RL_ALLOC_AVAILABLE = True
except Exception as e:
    RL_ALLOC_AVAILABLE = False
    print(f"⚠️ RLPortfolioAllocator no disponible: {e}")

logger = logging.getLogger("NAANOBOT_FTMO")


class BotOrchestrator:
    """
    Centraliza la lógica de decisión del bot multilayer.
    Se integra en el loop principal de run_live.py como un gestor no invasivo:
    el bot original (HIVE V5) sigue operando cuando el régimen es TREND.
    """

    SPIKE_COOLDOWN_MINUTES = 30  # Minutos de pausa tras deteccióm de SPIKE

    def __init__(self, mt5_client=None):
        self.mt5             = mt5_client
        self.regime_detector = RegimeDetector()
        self.safe_haven      = SafeHavenModule()
        self.mean_reversion  = MeanReversionModule()

        # RL Portfolio Allocator — Prioridad 1 L-H-N
        self.rl_allocator = RLPortfolioAllocator() if RL_ALLOC_AVAILABLE else None

        self.current_regime     = "TREND"
        self.current_weights    = {"trend_weight": 1.0, "crisis_weight": 0.0, "range_weight": 0.0}
        self.spike_triggered_at = None
        self._initialized       = False

        logger.info("🎼 BOT ORCHESTRATOR: All-Weather + RL Allocator Initialized.")
        logger.info(f"  RL Allocator: {'✅ ACTIVE' if self.rl_allocator else '⚠️ DISABLED'}")

    # ------------------------------------------------------------------
    # MÉTODO PRINCIPAL: llamado en cada ciclo del loop
    # ------------------------------------------------------------------
    def evaluate(self, df, gold_df=None) -> dict:
        """
        df      → DataFrame del par actualmente escaneado
        gold_df → DataFrame de XAUUSD para detección de crisis
        kwargs  → Opcionales: daily_pnl_pct (float)
        """
        # 1. Detectar régimen actual
        regime = self.regime_detector.detect(df, gold_df)
        prev   = self.current_regime
        self.current_regime = regime

        if regime != prev:
            logger.info(f"🔄 RÉGIMEN CAMBIÓ: {prev} → {regime}")
            if prev == "CRISIS":
                self.safe_haven.reset_cycle()

        # 2. RL Portfolio Allocator: pesos óptimos de capital
        adx       = float(df.iloc[-1].get("adx", 25.0)) if df is not None and len(df) > 0 else 25.0
        atr       = float(df.iloc[-1].get("atr", 0.001)) if df is not None and len(df) > 0 else 0.001
        avg_atr   = float(df["atr"].tail(20).mean()) if (df is not None and "atr" in df.columns) else atr
        atr_ratio = atr / max(avg_atr, 1e-9)
        daily_pnl = kwargs.get("daily_pnl_pct", 0.0)

        if self.rl_allocator:
            weights = self.rl_allocator.decide(regime, adx, atr_ratio, daily_pnl)
            self.current_weights = weights
        else:
            weights = {"trend_weight": 1.0, "crisis_weight": 0.0, "range_weight": 0.0}

        result = {
            "regime":          regime,
            "allow_hive":      False,
            "mr_signal":       None,
            "sh_signals":      [],
            "protect_tickets": [],
            "weights":         weights,
            "reason":          ""
        }

        # 2. SPIKE: pausa total, sin nuevas posiciones
        if regime == "SPIKE":
            self._handle_spike()
            if self._in_spike_cooldown():
                result["reason"] = f"SPIKE cooldown activo ({self.SPIKE_COOLDOWN_MINUTES}m)"
                return result
            else:
                # Cooldown expirado → volver a TREND
                self.current_regime = "TREND"
                regime = "TREND"

        # 3. CRISIS: Safe Haven activo, HIVE V5 detenido
        if regime == "CRISIS":
            positions = self.mt5.positions_get() if self.mt5 else []
            positions = list(positions) if positions else []

            result["sh_signals"]      = self.safe_haven.evaluate_entries({})  # se pobla con datos reales en loop
            result["protect_tickets"] = self.safe_haven.evaluate_existing_positions(positions)
            result["reason"]          = "Mode CRISIS: Safe Haven activo. HIVE V5 detenido."
            return result

        # 4. RANGE: Mean Reversion activo, HIVE V5 en modo filtrado
        if regime == "RANGE":
            if df is not None:
                df_bb = self.mean_reversion.calculate_bollinger(df)
                symbol = str(df.attrs.get("symbol", "UNKNOWN"))
                mr_signal = self.mean_reversion.scan_entries(df_bb, symbol)
                result["mr_signal"] = mr_signal
            result["reason"] = "Mode RANGE: Mean Reversion activo. HIVE V5 en standby."
            return result

        # 5. TREND: HIVE V5 opera con normalidad total
        result["allow_hive"] = True
        result["reason"]     = f"Mode TREND: HIVE V5 activo. ADX confirma dirección."
        return result

    # ------------------------------------------------------------------
    # HELPERS INTERNOS
    # ------------------------------------------------------------------
    def _handle_spike(self):
        if self.spike_triggered_at is None:
            self.spike_triggered_at = datetime.now(timezone.utc)
            logger.warning(f"💥 SPIKE detectado. Cooldown de {self.SPIKE_COOLDOWN_MINUTES} min activado.")

    def _in_spike_cooldown(self) -> bool:
        if self.spike_triggered_at is None:
            return False
        elapsed = (datetime.now(timezone.utc) - self.spike_triggered_at).total_seconds() / 60
        if elapsed >= self.SPIKE_COOLDOWN_MINUTES:
            self.spike_triggered_at = None
            logger.info("✅ SPIKE cooldown expirado. Reanudando operaciones.")
            return False
        logger.info(f"⏱️ SPIKE cooldown: {elapsed:.1f}/{self.SPIKE_COOLDOWN_MINUTES} min")
        return True

    def status_report(self) -> str:
        """Genera una línea de estado para los logs y Telegram."""
        cooldown = ""
        if self.spike_triggered_at and self._in_spike_cooldown():
            elapsed = (datetime.now(timezone.utc) - self.spike_triggered_at).total_seconds() / 60
            cooldown = f" | Spike Cooldown: {elapsed:.0f}m"
        return f"🎼 Orchestrator: {self.current_regime}{cooldown}"
