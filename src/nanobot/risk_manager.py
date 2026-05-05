import json
import logging
import os

logger = logging.getLogger("Nanobot.RiskManager")

# Ruta al AffinityMap (Single Source of Truth)
_AFFINITY_MAP_PATH = "data/research/affinity_map.json"

class MeritocraticRiskManager:
    def __init__(self, mt5_client, global_cap=0.025):
        self.mt5 = mt5_client
        self.GLOBAL_CAP = global_cap
        self.transit_risk = 0.0  # Riesgo aprobado en el micro-ciclo actual
        logger.info(f"⚖️ [RISK TRIBUNAL] Inicializado con Global Cap: {global_cap*100:.2f}%")
        
    def calculate_floating_risk(self, positions, account_info, fallback_atr_dict):
        """
        Calcula el riesgo comprometido forense. Implementa el BLINDAJE NÉMESIS 
        contra SL asíncronos (0.0) inyectando 2.0 ATR de emergencia.
        """
        total_risk_usd = 0.0
        
        if not positions:
            return 0.0
            
        for p in positions:
            symbol = p.symbol
            sym_info = self.mt5.symbol_info(symbol)
            
            # Protección contra fallos de socket de la API
            if sym_info is None:
                logger.warning(f"No se pudo obtener sym_info para {symbol}. Omitiendo cálculo exacto, riesgo subestimado.")
                continue
                
            tick_value = sym_info.trade_tick_value
            point = sym_info.point
            
            sl_price = p.sl
            # BLINDAJE NÉMESIS: Si el SL es 0.0, usamos el fallback (2.0 * ATR)
            if sl_price == 0.0:
                atr = fallback_atr_dict.get(symbol, 0.0015) # Default 15 pips si no hay ATR
                sl_price = p.price_open - (atr * 2.0) if p.type == 0 else p.price_open + (atr * 2.0)
            
            # Cálculo exacto de distancia en la moneda de la cuenta (USD)
            dist_points = abs(p.price_open - sl_price) / (point + 1e-12)
            risk_usd = p.volume * dist_points * tick_value
            total_risk_usd += risk_usd
            
        return total_risk_usd / account_info.equity if account_info and account_info.equity > 0 else 0.0

    def get_meritocratic_risk(self, symbol, symbol_data, base_risk, available_cap, current_hour=None, current_spread_pips=None, symbol_atr_pips=None, stasis=False):
        """
        Tribunal de Asignación V9.1: Aplica el Multiplicador Bayesiano 3D, 
        Filtro de Liquidez y la Guillotina FTMO + Capa de Soberanía.
        """
        if stasis:
            logger.info(f"🛡️ [SOVEREIGNTY STASIS] {symbol} | Operativa bloqueada por meta diaria cumplida (MVA).")
            return 0.0

        reco = symbol_data.get("reco", "NEM1 (Trend)")
        role = "NEM2" if "Antith" in reco else "NEM1"
        
        # Extraer datos del rol activo
        role_data = symbol_data.get(role, {})
        scn = role_data.get("n", 0)
        sum_r = role_data.get("sum_r", 0.0)
        
        # 0. FILTRO DE LIQUIDEZ TÉRMICA (Vector 1)
        if current_spread_pips is not None and symbol_atr_pips is not None:
            # Si el spread es > 20% del ATR, el riesgo es 0 (SILENT MODE)
            if current_spread_pips > (0.20 * symbol_atr_pips):
                logger.warning(f"🚫 [LIQUIDITY FILTER] {symbol} spread ({current_spread_pips:.1f}) > 20% ATR ({0.2*symbol_atr_pips:.1f}). SILENT MODE.")
                return 0.0

        # 1. Multiplicador Alpha Bayesiano (Tensor 3D)
        multiplier = 1.0
        edge = 0.0
        
        # Primero intentar mérito horario (Matriz de Cuarentena Dinámica)
        if current_hour is not None and "hourly" in role_data:
            hour_key = str(current_hour)
            h_data = role_data["hourly"].get(hour_key, {"n": 0, "sum_r": 0.0})
            if h_data["n"] >= 3:
                h_edge = h_data["sum_r"] / h_data["n"]
                if h_edge <= -0.3: 
                    multiplier = 0.20 # Cuarentena Horaria
                    logger.info(f"⏳ [HOURLY QUARANTINE] {symbol} Hour {current_hour} | Edge: {h_edge:.2f}R")
                elif h_edge > 0.4:
                    multiplier = 1.50 # Impulso Horario
        
        # Si no hay cuarentena horaria, usar mérito general
        if multiplier == 1.0 and scn >= 5:
            edge = sum_r / scn
            if role == "NEM1": # Tendencia
                if edge <= -0.2: multiplier = 0.20    # Cuarentena General
                elif edge < 0.0: multiplier = 0.50    # Leve castigo
                elif edge > 0.3: multiplier = 2.00    # Esteroides Alpha
            else:
                multiplier = 1.00 # NEM2: Reversión perdonada
        elif scn < 5 and multiplier == 1.0:
            multiplier = 0.50 # Sonda de descubrimiento
            
        target_risk = base_risk * multiplier
        
        # 2. Guillotina FTMO (Global Cap)
        available_budget = max(0.0, available_cap - self.transit_risk)
        adjusted_risk = min(target_risk, available_budget)
        
        # 3. El Pasaporte de Riesgo (Audit Log)
        status = f"CHOKED to {adjusted_risk*100:.2f}% (Budget Limit)" if adjusted_risk < target_risk else "APPROVED"
        logger.info(f"[RISK PASSPORT] {symbol} | Role: {role} | Multiplier: {multiplier}x | Status: {status}")
        
        return max(0.0, adjusted_risk)

    def get_omega_core_allocation(self, symbol: str, role: str, account_equity: float,
                                  max_risk_pct: float = 0.01) -> dict:
        """
        [v10.0.0] OMEGA CORE: ENRUTADOR MAESTRO DEL 1%
        ================================================
        Consulta el VitalityOracle y calcula la distribución asimétrica del riesgo
        disponible entre los 7 niveles de la MegaGrid.

        Reglas:
          - Si el sistema está en COMA → bloqueo total, todos a Scout (0.01)
          - Si un nivel está en CUARENTENA (N<30) → Scout (0.01), sin riesgo real
          - Si un nivel está INFECTADO (PF<1.2) → Scout (0.01), peso=0
          - El presupuesto restante se distribuye proporcionalmente a V_L de sanos

        Args:
            symbol:         Símbolo a operar (ej. "EURUSD")
            role:           Rol activo ("NEM1" o "NEM2")
            account_equity: Equity actual de la cuenta en USD
            max_risk_pct:   Techo global de riesgo (default 1%)

        Returns:
            {
              "level_risks": {"L1": 0.0, "L2": 12.4, ..., "L7": 47.0},  ← USD por nivel
              "health":      str,     ← Estado del sistema ("ALPHA"/"SALUDABLE"/...)
              "v_global":    float,   ← Signo vital global
              "scout_only":  bool,    ← True = todos en cuarentena, usar 0.01 lotes
              "weights":     dict,    ← Pesos normalizados por nivel
            }
        """
        try:
            from nanobot.vitality_oracle import VitalityOracle
        except ImportError:
            logger.error("❌ [OMEGA CORE] VitalityOracle no disponible. Usando riesgo plano.")
            return self._fallback_allocation(account_equity, max_risk_pct)

        # --- CARGAR MAPA DE AFINIDAD ---
        affinity_map = {}
        if os.path.exists(_AFFINITY_MAP_PATH):
            try:
                with open(_AFFINITY_MAP_PATH, "r") as f:
                    affinity_map = json.load(f)
            except Exception as e:
                logger.warning(f"⚠️ [OMEGA CORE] Error leyendo AffinityMap: {e}")

        oracle = VitalityOracle()

        # --- DIAGNÓSTICO COMPLETO ---
        diagnosis = oracle.full_diagnosis(affinity_map, symbol, role)
        global_health = diagnosis["global_health"]
        role_diagnosis = diagnosis["role_diagnosis"]

        health_str = global_health["health"]
        v_global   = global_health["v_global"]
        weights    = role_diagnosis["weights"]

        # --- PRESUPUESTO DISPONIBLE ---
        max_risk_usd = account_equity * max_risk_pct

        # --- REGLA 1: SISTEMA EN COMA → BLOQUEO TOTAL ---
        if health_str == "COMA":
            logger.warning(
                f"🚨 [OMEGA CORE] V_Global={v_global:.4f} → COMA. "
                f"Riesgo bloqueado. Solo Scouts de exploración."
            )
            return {
                "level_risks": {f"L{i}": 0.0 for i in range(1, 8)},
                "health":      health_str,
                "v_global":    v_global,
                "scout_only":  True,
                "weights":     weights,
            }

        # --- REGLA 2: TODOS EN CUARENTENA → MODO BIOPSIA ---
        total_force = role_diagnosis["total_force"]
        if total_force == 0:
            logger.info(
                f"⚗️ [OMEGA CORE] {symbol}/{role}: Sin niveles sanos aún. "
                f"Modo Biopsia (0.01 lotes en todos)."
            )
            return {
                "level_risks": {f"L{i}": 0.0 for i in range(1, 8)},
                "health":      health_str,
                "v_global":    v_global,
                "scout_only":  True,
                "weights":     weights,
            }

        # --- REGLA 3: DISTRIBUCIÓN ASIMÉTRICA DEL PRESUPUESTO ---
        # Costo de los Scouts (niveles no sanos que igual se disparan a 0.01)
        # Por simplicidad, asumimos que el costo de cada scout es mínimo y no se
        # descuenta del presupuesto (los scouts usan su propio lote mínimo fijo)
        level_risks = {}
        for lk in [f"L{i}" for i in range(1, 8)]:
            weight = weights.get(lk, 0.0)
            if weight > 0:
                level_risks[lk] = round(max_risk_usd * weight, 4)
            else:
                level_risks[lk] = 0.0  # INFECTADO o CUARENTENA → Scout (sin USD real)

        # --- AUDIT LOG ---
        healthy = role_diagnosis["healthy_count"]
        quarant = role_diagnosis["quarantine_count"]
        logger.info(
            f"💰 [OMEGA CORE] {symbol}/{role} | Health: {health_str} | V_Global: {v_global:.4f} | "
            f"Presupuesto: ${max_risk_usd:.2f} | Niveles sanos: {healthy}/7 | En cuarentena: {quarant}"
        )
        for lk, usd in level_risks.items():
            status = role_diagnosis["levels"].get(lk, {}).get("status", "?")
            v_l    = role_diagnosis["levels"].get(lk, {}).get("v_l", 0.0)
            if usd > 0:
                logger.info(f"   {lk}: ${usd:.2f} (V_L={v_l:.4f} | {status})")
            else:
                logger.debug(f"   {lk}: Scout 0.01 lotes ({status})")

        return {
            "level_risks": level_risks,
            "health":      health_str,
            "v_global":    v_global,
            "scout_only":  False,
            "weights":     weights,
        }

    def _fallback_allocation(self, equity: float, max_risk_pct: float) -> dict:
        """Distribución plana de emergencia si el Oráculo no está disponible."""
        per_level = round(equity * max_risk_pct / 7, 4)
        return {
            "level_risks": {f"L{i}": per_level for i in range(1, 8)},
            "health":      "SALUDABLE",
            "v_global":    1.0,
            "scout_only":  False,
            "weights":     {f"L{i}": round(1/7, 4) for i in range(1, 8)},
        }

    def check_virtual_stops(self, position, current_bid, current_ask, current_hour):
        """
        Protocolo STEALTH AEGIS: Gestión de SL Virtual por Mid-Price
        para evitar barridos de spread en Rollover.
        """
        mid_price = (current_bid + current_ask) / 2.0
        current_spread = (current_ask - current_bid)
        
        # Extraer virtual_sl del comentario si no está en el objeto
        virtual_sl = getattr(position, 'virtual_sl', 0.0)
        if virtual_sl == 0.0 and hasattr(position, 'comment'):
            # Formato esperado: ..._VSL1.12345
            import re
            match = re.search(r"_VSL([\d.]+)", position.comment)
            if match:
                virtual_sl = float(match.group(1))

        if virtual_sl == 0.0: return "SAFE"
        
        is_hit = (position.type == 0 and mid_price <= virtual_sl) or \
                 (position.type == 1 and mid_price >= virtual_sl)
        
        if is_hit:
            # Si es hora de Rollover (23 o 0) y el spread es alto, HOLD.
            # Umbral de toxicidad: spread > 3x del spread normal o > 15 pips
            if current_hour in [23, 0] and current_spread > 0.0015: 
                logger.warning(f"🛡️ [STEALTH AEGIS] {position.symbol} SL hit by MidPrice but Spread is toxic ({current_spread:.5f}). HOLDING.")
                return "HOLD"
            return "CLOSE"
            
        return "SAFE"

    def commit_risk(self, risk_pct):
        self.transit_risk += risk_pct

    def reset_cycle(self):
        self.transit_risk = 0.0
