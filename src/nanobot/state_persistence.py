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
        """Carga el estado físico del disco usando SecureDB y asegura que todas las llaves existan."""
        defaults = {
            "daily_start_balance": 0.0,
            "equity_peak": 0.0,
            "last_reset_date": "",
            "last_reset_week": 0,
            "weekly_start_balance": 0.0,
            "weekly_equity_peak": 0.0,
            "weekly_floor_active": False,
            "trust_tier": 1,
            "consecutive_baskets": 0,
            "daily_goal_reached": False,
            "rollover_lock": False,
            "reversal_profile": {}, 
            "version": "1.6.0"
        }
        state = db.load_json(self.file_path, default=defaults)
        
        # Merge defaults for missing keys (v7.5.0 Migration)
        updated = False
        for k, v in defaults.items():
            if k not in state:
                state[k] = v
                updated = True
        
        if updated:
            db.save_json(self.file_path, state)
            
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

        # 1. LÓGICA DE DESCENSO (Castigo Estricto por Drawdown de Equidad)
        loss_limit = -(start_balance * 0.005)
        if pnl_usd < loss_limit:
            if current_tier > 1 or consecutive > 0:
                logger.warning(f"📉 [DEMOTION] PnL (${pnl_usd:,.2f}) superó límite de seguridad FTMO (${loss_limit:,.2f}). Fondeo revocado al Nivel 1.")
                self.state["trust_tier"] = 1
                self.state["consecutive_baskets"] = 0
                self.save()
            return

        # 2. LÓGICA DE ASCENSO (Promoción por Méritos Reales)
        # Solo se otorga el punto si la canasta cerró con éxito Y el beneficio es tangible (>0).
        if is_basket_win:
            if pnl_usd > 0:
                consecutive += 1
                logger.info(f"🏆 [BASKET WIN] Mesa Limpia Confirmada. Beneficio Tangible: ${pnl_usd:,.2f}. Progreso: {consecutive}/3.")
                
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
            else:
                logger.warning(f"⚠️ [PROMOTION DENIED] Intento de ascenso con PnL no positivo (${pnl_usd:,.2f}). El punto de mérito no fue otorgado.")


    def get_trust_threshold_pct(self):
        """Retorna el porcentaje de Lock basado en el Tier actual."""
        tier_map = {
            1: 0.25, # Rango 1: A Prueba
            2: 0.50, # Rango 2: Consistente
            3: 0.75, # Rango 3: Confiable
            4: 1.00  # Rango 4: Maestría (Hard Cap)
        }
        return tier_map.get(self.state.get("trust_tier", 1), 0.25)

    def get_trust_risk_pct(self):
        """Retorna el porcentaje de riesgo por operación basado en el Tier actual (v7.2.0)."""
        risk_map = {
            1: 0.0015, # 0.15% (Tímido / Supervivencia)
            2: 0.0025, # 0.25% (Consistencia)
            3: 0.0035, # 0.35% (Crecimiento)
            4: 0.0050  # 0.50% (Maestría)
        }
        return risk_map.get(self.state.get("trust_tier", 1), 0.0015)

    def validate_and_sync(self, current_balance, current_equity):
        """
        Sincronización Atómica con Sanity Check.
        Evita que errores de conexión de MT5 arruinen el balance inicial.
        """
        now = datetime.utcnow()
        today_str = now.strftime('%Y-%m-%d')
        current_week = now.isocalendar()[1]
        needs_save = False
        
        # 0. SANITY CHECK: ¿Es el balance actual real?
        if not db.validate_account_data(current_balance, self.state.get("daily_start_balance", 0)):
            logger.error("🛑 DATO DE BALANCE SOSPECHOSO RECHAZADO. Manteniendo estado previo.")
            return self.state

        # 1. DETECCIÓN DE CAMBIO DE DÍA (Daily Reset para FTMO con Reloj del Búnker)
        if self.state.get("last_reset_date") != today_str:
            # Protocolo de Hibernación: Solo resetear si ha pasado la zona de peligro de spread (02:00 AM)
            if now.hour >= 2:
                logger.info(f"⏳ [UTC RESET] Nuevo día: {today_str}. Zona segura alcanzada. Reiniciando objetivo diario.")
                self.state["daily_goal_reached"] = False
                self.state["daily_start_balance"] = current_balance
                self.state["last_reset_date"] = today_str
                needs_save = True
            else:
                # El día cambió pero seguimos en hibernación por seguridad
                if int(time.time()) % 3600 < 5: # Log cada hora
                    logger.warning(f"🛡️ [BUNKER MODE] Día {today_str} detectado, pero esperando a las 02:00 UTC para normalización de spread.")

        # 2. DETECCIÓN DE CAMBIO DE SEMANA (v7.5.0)
        if self.state.get("last_reset_week") != current_week:
            logger.info(f"📅 [WEEKLY RESET] Nueva semana: {current_week}. Fijando ancla semanal.")
            self.state["weekly_start_balance"] = current_balance
            self.state["weekly_equity_peak"] = current_equity
            self.state["weekly_floor_active"] = False
            self.state["last_reset_week"] = current_week
            needs_save = True

        # 3. SEGUIMIENTO DE PICOS (High Watermark)
        if current_equity > self.state.get("equity_peak", 0):
            self.state["equity_peak"] = current_equity
            needs_save = True
        
        if current_equity > self.state.get("weekly_equity_peak", 0):
            self.state["weekly_equity_peak"] = current_equity
            needs_save = True

        # 4. SEGURIDAD: Inicialización si es necesario
        if self.state.get("weekly_start_balance", 0) <= 0:
            self.state["weekly_start_balance"] = current_balance
            needs_save = True

        if needs_save:
            self.save()

        return self.state

    def update_reversal_profile(self, symbol, atr_dist):
        """[Fase 4] Registra una distancia ATR de reversión exitosa."""
        if "reversal_profile" not in self.state:
            self.state["reversal_profile"] = {}
        
        if symbol not in self.state["reversal_profile"]:
            self.state["reversal_profile"][symbol] = []
            
        self.state["reversal_profile"][symbol].append(round(float(atr_dist), 2))
        
        # Mantener solo las últimas 100 muestras para adaptabilidad
        if len(self.state["reversal_profile"][symbol]) > 100:
            self.state["reversal_profile"][symbol] = self.state["reversal_profile"][symbol][-100:]
            
        self.save()

    def save(self):
        """Persistencia física atómica delegada al SecureDB Manager."""
        db.save_json(self.file_path, self.state)

    def get_daily_drawdown_pct(self, current_equity):
        """Calcula el Drawdown real relativo al inicio del día del servidor."""
        start = self.state["daily_start_balance"]
        if start <= 0: return 0.0
        return (current_equity - start) / start
