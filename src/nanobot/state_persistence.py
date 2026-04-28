import json
import os
import time
from datetime import datetime
import logging
from nanobot.utils.database import SecureDatabaseManager as db

# Configure logging
logger = logging.getLogger("PERSISTENCE")

class StatePersistence:
    """
    Guardián de la Realidad OMEGA+: Gestiona el estado térmico y la memoria 
    persistente de la equidad para garantizar el cumplimiento de FTMO tras reinicios.
    - [v6.6.3] Integración DBA: Escritura Atómica y Sanity Checks.
    """
    def __init__(self, file_path="config/state_persistence.json"):
        self.file_path = file_path
        self.state = self._load_initial_state()

    def _load_initial_state(self):
        """Carga el estado físico del disco usando SecureDB."""
        state = db.load_json(self.file_path, default={
            "daily_start_balance": 0.0,
            "equity_peak": 0.0,
            "last_reset_date": "",
            "trust_tier": 1,               # [NEW v6.7.0] Nivel de confianza (1 a 4)
            "consecutive_baskets": 0,      # [NEW v6.7.0] Contador para ascenso
            "version": "1.3.0"
        })
        if state.get("daily_start_balance", 0) > 0:
            logger.info(f"✅ Memoria de estado recuperada: Inicio Día ${state['daily_start_balance']:,.2f}")
            logger.info(f"🛡️ TRUST TIER: {state.get('trust_tier', 1)} | Victorias: {state.get('consecutive_baskets', 0)}/3")
        return state

    def evaluate_performance(self, pnl_usd, is_basket_win=False):
        """
        [DYNAMIC TRUST RATCHET]
        Evalúa el desempeño diario para decidir ascensos o denegaciones estrictas.
        """
        current_tier = self.state.get("trust_tier", 1)
        consecutive = self.state.get("consecutive_baskets", 0)
        start_balance = self.state.get("daily_start_balance", 0.0)
        
        if start_balance <= 0: return

        # 1. LÓGICA DE DESCENSO (Castigo Estricto por Drawdown)
        if pnl_usd < -(start_balance * 0.005):
            if current_tier > 1 or consecutive > 0:
                logger.warning(f"📉 [DEMOTION] Límite de pérdida superado ({-0.5}%). Fondeo revocado al Nivel 1.")
                self.state["trust_tier"] = 1
                self.state["consecutive_baskets"] = 0
                self.save()
            return

        # 2. LÓGICA DE ASCENSO (Promoción por Méritos)
        if is_basket_win:
            consecutive += 1
            logger.info(f"🏆 [BASKET WIN] Punto de confianza otorgado. Progreso al nuevo nivel: {consecutive}/3.")
            
            if consecutive >= 3:
                if current_tier < 4:
                    current_tier += 1
                    consecutive = 0
                    logger.info(f"🎖️ [PROMOTION] Ascenso a TIER {current_tier} Autorizado. Incrementando Riesgo.")
                else:
                    logger.info("💎 [MASTERY] El Bot está operando en el Techo Funcional (Tier 4, 1.00%).")
                    consecutive = 3 # Hard limit
            
            self.state["trust_tier"] = current_tier
            self.state["consecutive_baskets"] = consecutive
            self.save()

    def get_trust_threshold_pct(self):
        """Retorna el porcentaje de Lock basado en el Tier actual."""
        tier_map = {
            1: 0.25, # Rango 1: A Prueba
            2: 0.50, # Rango 2: Consistente
            3: 0.75, # Rango 3: Confiable
            4: 1.00  # Rango 4: Maestría (Hard Cap)
        }
        return tier_map.get(self.state.get("trust_tier", 1), 0.25)

    def validate_and_sync(self, current_balance, current_equity):
        """
        Sincronización Atómica con Sanity Check.
        Evita que errores de conexión de MT5 arruinen el balance inicial.
        """
        today_str = datetime.utcnow().strftime('%Y-%m-%d')
        needs_save = False
        
        # 0. SANITY CHECK: ¿Es el balance actual real?
        if not db.validate_account_data(current_balance, self.state["daily_start_balance"]):
            # Si el dato es sospechoso, usamos el último guardado seguro
            logger.error("🛑 DATO DE BALANCE SOSPECHOSO RECHAZADO. Manteniendo estado previo para proteger Regla FTMO.")
            return self.state

        # 1. DETECCIÓN DE CAMBIO DE DÍA (Daily Reset para FTMO)
        if self.state["last_reset_date"] != today_str:
            logger.info(f"⏳ [UTC RESET] Nuevo día detectado: {today_str}. Fijando balance inicial FTMO.")
            self.state["daily_start_balance"] = current_balance
            self.state["last_reset_date"] = today_str
            needs_save = True

        # 2. SEGUIMIENTO DE PICO DE EQUIDAD (Memory of Success)
        if current_equity > self.state["equity_peak"]:
            self.state["equity_peak"] = current_equity
            needs_save = True

        # 3. SEGURIDAD ADICIONAL: Si el balance inicial es 0, forzar sync
        if self.state["daily_start_balance"] <= 0:
            self.state["daily_start_balance"] = current_balance
            needs_save = True

        if needs_save:
            self.save()

        return self.state

    def save(self):
        """Persistencia física atómica delegada al SecureDB Manager."""
        db.save_json(self.file_path, self.state)

    def get_daily_drawdown_pct(self, current_equity):
        """Calcula el Drawdown real relativo al inicio del día del servidor."""
        start = self.state["daily_start_balance"]
        if start <= 0: return 0.0
        return (current_equity - start) / start
