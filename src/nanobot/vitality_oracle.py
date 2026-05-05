"""
VITALITY ORACLE - OMEGA+ v10.0.0
=================================
Módulo de diagnóstico estadístico clínico para el Omega Core.
Transforma el historial de trades por nivel en métricas resistentes a la suerte.

Métricas:
  - WR_pessimistic: Wilson Score (límite inferior de confianza del Win Rate)
  - PF_clinical:    Profit Factor Winsorizado (top 5% de ganancias amputado)
  - V_L:            Índice de Vitalidad por Nivel = WR_pessimistic × PF_clinical
  - V_Global:       Signo Vital Global del sistema (COMA / UCI / SALUDABLE / ALPHA)

Filosofía:
  Un nivel con N=3 y WR=100% no es un héroe, es una muestra insuficiente.
  Un nivel con PF=8.5 por un solo Flash Crash no es eficiente, es afortunado.
  Solo se inyecta capital donde el mérito es REPLICABLE y ESTADÍSTICAMENTE VÁLIDO.
"""

import math
import logging

logger = logging.getLogger("Nanobot.VitalityOracle")

# --- CONSTANTES DEL ORÁCULO ---

QUARANTINE_MIN_SAMPLES = 30    # N mínimo por nivel para salir de cuarentena
MINIMUM_VIABLE_PF      = 1.20  # PF mínimo para que un nivel sea "Sano"
WINSOR_PERCENTILE      = 0.95  # Amputar ganancias por encima del percentil 95
CONFIDENCE_Z           = 1.645 # Z para intervalo de confianza del 95% (una cola)

# Estados de vida del sistema
HEALTH_COMA      = "COMA"      # V_Global < 1.0  → bloqueo total
HEALTH_UCI       = "UCI"       # 1.0 ≤ V_G < 1.15 → solo Scouts (0.01)
HEALTH_SALUDABLE = "SALUDABLE" # 1.15 ≤ V_G < 1.4 → riesgo normal
HEALTH_ALPHA     = "ALPHA"     # V_G ≥ 1.4       → 1% completo activado


class VitalityOracle:
    """
    El Juez Estadístico del Omega Core.
    Lee los datos granulares del AffinityMap (Fase 1) y emite veredictos
    de vitalidad por nivel y por sistema.
    """

    # ------------------------------------------------------------------
    # MÓDULO 1: WIN RATE PESIMISTA (Wilson Score)
    # ------------------------------------------------------------------

    @staticmethod
    def wilson_lower_bound(wins: int, n: int, z: float = CONFIDENCE_Z) -> float:
        """
        Calcula el límite inferior del intervalo de Wilson para el Win Rate.

        Ejemplo:
          - N=3, wins=3  → WR_raw=100%, WR_pesimista ≈ 40%  ← Castigado por muestra pequeña
          - N=50, wins=35 → WR_raw=70%,  WR_pesimista ≈ 59%  ← Confianza real
          - N=0           → retorna 0.0 (sin datos, sin permiso)

        Args:
            wins: Número de trades ganadores.
            n:    Total de trades cerrados en el nivel.
            z:    Factor Z para el nivel de confianza (default 95%).

        Returns:
            float: WR pesimista entre 0.0 y 1.0
        """
        if n == 0:
            return 0.0

        p = wins / n
        z2 = z * z
        denominator = 1.0 + z2 / n
        center = p + z2 / (2 * n)
        margin = z * math.sqrt(p * (1.0 - p) / n + z2 / (4 * n * n))
        return max(0.0, (center - margin) / denominator)

    # ------------------------------------------------------------------
    # MÓDULO 2: PROFIT FACTOR CLÍNICO (Winsorización)
    # ------------------------------------------------------------------

    @staticmethod
    def clinical_profit_factor(profit_history: list) -> float:
        """
        Calcula el Profit Factor eliminando el top 5% de ganancias.

        Razón: Un solo trade en un Flash Crash puede inflar el PF artificialmente.
        Al amputar el percentil 95 de las ganancias, solo medimos el tejido sano
        y replicable de la estrategia.

        Ejemplo:
          - Ganancias: [1.2, 1.8, 0.9, 45.0, 2.1] ← 45.0 es el milagro
          - Después de Winsorización tope en 95%: [1.2, 1.8, 0.9, 2.2, 2.1]
          - Pérdidas: [-0.8, -1.0, -0.7]
          - PF_clínico = (1.2+1.8+0.9+2.2+2.1) / (0.8+1.0+0.7) = 8.2/2.5 = 3.28
          - (vs PF_bruto que hubiese sido (1.2+1.8+0.9+45.0+2.1)/2.5 = 20.4)

        Args:
            profit_history: Lista de beneficios netos por trade (positivos y negativos).

        Returns:
            float: PF clínico. Retorna 0.0 si no hay suficientes datos.
        """
        if not profit_history or len(profit_history) < 3:
            return 0.0

        wins   = [p for p in profit_history if p > 0]
        losses = [p for p in profit_history if p < 0]

        if not wins or not losses:
            # No hay pérdidas → infinito teórico, pero sin suficiente historia es sospechoso
            return 99.0 if not losses and len(wins) >= QUARANTINE_MIN_SAMPLES else 0.0

        # --- AMPUTACIÓN DEL PERCENTIL 95 ---
        # Calculamos el umbral de corte sin numpy (compatible con cualquier entorno)
        sorted_wins = sorted(wins)
        percentile_idx = int(len(sorted_wins) * WINSOR_PERCENTILE)
        win_cap = sorted_wins[percentile_idx - 1] if percentile_idx > 0 else sorted_wins[-1]

        # Aplicamos el tope: las ganancias mayores al percentil 95 se recortan
        winsorized_wins = [min(w, win_cap) for w in wins]

        gross_profit = sum(winsorized_wins)
        gross_loss   = abs(sum(losses))

        if gross_loss == 0:
            return 99.0

        return round(gross_profit / gross_loss, 4)

    # ------------------------------------------------------------------
    # MÓDULO 3: ÍNDICE DE VITALIDAD POR NIVEL (V_L)
    # ------------------------------------------------------------------

    def evaluate_level(self, level_data: dict) -> dict:
        """
        Calcula el diagnóstico clínico completo de un nivel (L1..L7).

        Returns un dict con:
          - wr_pessimistic: float
          - pf_clinical:    float
          - v_l:            float (el índice de vitalidad)
          - status:         str  ("ALPHA"/"SALUDABLE"/"CUARENTENA"/"INFECTADO")
          - n:              int  (tamaño de muestra)
          - quarantine:     bool (True si N < 30)
        """
        n              = level_data.get("n", 0)
        wins           = level_data.get("wins", 0)
        profit_history = level_data.get("profit_history", [])

        # --- PASO 1: CUARENTENA ESTADÍSTICA ---
        if n < QUARANTINE_MIN_SAMPLES:
            logger.debug(f"⚗️ [ORACLE] Nivel en cuarentena: N={n} < {QUARANTINE_MIN_SAMPLES} mínimo.")
            return {
                "wr_pessimistic": 0.0,
                "pf_clinical":    0.0,
                "v_l":            0.0,
                "status":         "CUARENTENA",
                "n":              n,
                "quarantine":     True
            }

        # --- PASO 2: CÁLCULO CLÍNICO ---
        wr_p = self.wilson_lower_bound(wins, n)
        pf_c = self.clinical_profit_factor(profit_history)
        v_l  = round(wr_p * pf_c, 4)

        # --- PASO 3: TRIAJE ---
        if pf_c < MINIMUM_VIABLE_PF:
            status = "INFECTADO"    # PF insuficiente → degradado a Scout
            v_l = 0.0               # Su peso en el reparto del 1% es cero
        elif v_l >= 1.4:
            status = "ALPHA"
        elif v_l >= 1.15:
            status = "SALUDABLE"
        else:
            status = "UCI"

        logger.info(
            f"🔬 [ORACLE] Nivel → WR_p={wr_p:.2%} | PF_c={pf_c:.2f} | "
            f"V_L={v_l:.4f} | Status: {status} (N={n})"
        )

        return {
            "wr_pessimistic": round(wr_p, 4),
            "pf_clinical":    pf_c,
            "v_l":            v_l,
            "status":         status,
            "n":              n,
            "quarantine":     False
        }

    # ------------------------------------------------------------------
    # MÓDULO 4: DIAGNÓSTICO COMPLETO DE UN ACTIVO/ROL
    # ------------------------------------------------------------------

    def evaluate_role(self, role_data: dict) -> dict:
        """
        Evalúa todos los niveles L1-L7 de un rol (NEM1 o NEM2) y devuelve
        los pesos normalizados para el reparto del 1% de riesgo.

        Returns:
          {
            "levels": {
               "L1": {"v_l": 0.0, "status": "INFECTADO", ...},
               "L7": {"v_l": 1.85, "status": "ALPHA", ...},
               ...
            },
            "weights":      {"L1": 0.0, "L7": 0.45, ...},  ← Pesos normalizados
            "total_force":  float,   ← Suma de V_L de niveles sanos
            "healthy_count": int,
            "quarantine_count": int
          }
        """
        levels_raw = role_data.get("levels", {})
        all_levels = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]
        results    = {}
        total_force = 0.0
        healthy_count    = 0
        quarantine_count = 0

        for lk in all_levels:
            ldata  = levels_raw.get(lk, {"n": 0, "wins": 0, "profit_history": []})
            result = self.evaluate_level(ldata)
            results[lk] = result

            if result["quarantine"]:
                quarantine_count += 1
            elif result["status"] in ("ALPHA", "SALUDABLE"):
                healthy_count += 1
                total_force   += result["v_l"]

        # --- NORMALIZACIÓN DE PESOS ---
        # Cada nivel sano recibe un porcentaje del presupuesto proporcional a su V_L
        weights = {}
        for lk in all_levels:
            if total_force > 0 and not results[lk]["quarantine"] and results[lk]["v_l"] > 0:
                weights[lk] = round(results[lk]["v_l"] / total_force, 4)
            else:
                weights[lk] = 0.0

        return {
            "levels":          results,
            "weights":         weights,
            "total_force":     round(total_force, 4),
            "healthy_count":   healthy_count,
            "quarantine_count": quarantine_count
        }

    # ------------------------------------------------------------------
    # MÓDULO 5: SIGNO VITAL GLOBAL (V_Global)
    # ------------------------------------------------------------------

    def evaluate_global_health(self, affinity_map: dict) -> dict:
        """
        Calcula la salud sistémica de TODO el enjambre OMEGA+.

        Agrega los datos de todos los símbolos y roles para producir
        un V_Global que determina el estado de vida del bot.

        Args:
            affinity_map: El mapa de afinidad completo (leído del JSON).

        Returns:
          {
            "v_global":    float,
            "health":      str ("COMA"/"UCI"/"SALUDABLE"/"ALPHA"),
            "wr_global":   float,
            "pf_global":   float,
            "total_n":     int,
            "total_wins":  int,
            "all_profits": list
          }
        """
        total_n      = 0
        total_wins   = 0
        all_profits  = []

        for symbol, sym_data in affinity_map.items():
            # Saltamos claves que no son símbolos (ej. "reco")
            if not isinstance(sym_data, dict):
                continue
            for role in ["NEM1", "NEM2"]:
                role_data = sym_data.get(role, {})
                if not isinstance(role_data, dict):
                    continue
                levels = role_data.get("levels", {})
                for lk, ldata in levels.items():
                    if not isinstance(ldata, dict):
                        continue
                    total_n    += ldata.get("n", 0)
                    total_wins += ldata.get("wins", 0)
                    all_profits.extend(ldata.get("profit_history", []))

        # Calcular WR y PF global
        wr_global = self.wilson_lower_bound(total_wins, total_n) if total_n > 0 else 0.0
        pf_global = self.clinical_profit_factor(all_profits)
        v_global  = round(wr_global * pf_global, 4)

        # Determinar estado de vida
        if v_global < 1.0:
            health = HEALTH_COMA
        elif v_global < 1.15:
            health = HEALTH_UCI
        elif v_global < 1.4:
            health = HEALTH_SALUDABLE
        else:
            health = HEALTH_ALPHA

        logger.info(
            f"💓 [GLOBAL VITAL SIGNS] WR_G={wr_global:.2%} | PF_G={pf_global:.2f} | "
            f"V_Global={v_global:.4f} | HEALTH: {health} | Muestra total: N={total_n}"
        )

        return {
            "v_global":   v_global,
            "health":     health,
            "wr_global":  round(wr_global, 4),
            "pf_global":  pf_global,
            "total_n":    total_n,
            "total_wins": total_wins,
        }

    # ------------------------------------------------------------------
    # MÓDULO 6: INTERFAZ PRINCIPAL (FULL DIAGNOSIS)
    # ------------------------------------------------------------------

    def full_diagnosis(self, affinity_map: dict, symbol: str, role: str) -> dict:
        """
        Punto de entrada principal para el Risk Manager.

        Calcula:
          1. Los pesos de distribución del 1% para cada nivel del símbolo/rol.
          2. El estado de vida global del sistema.

        Args:
            affinity_map: El mapa de afinidad completo.
            symbol:       El símbolo a evaluar (ej. "EURUSD").
            role:         El rol a evaluar ("NEM1" o "NEM2").

        Returns:
          {
            "role_diagnosis": dict (resultado de evaluate_role),
            "global_health":  dict (resultado de evaluate_global_health),
            "risk_authorized": bool (True si el sistema permite operar con riesgo real)
          }
        """
        role_data = affinity_map.get(symbol, {}).get(role, {})
        role_diag = self.evaluate_role(role_data)
        global_diag = self.evaluate_global_health(affinity_map)

        # El riesgo real solo se autoriza si el sistema NO está en COMA
        risk_authorized = global_diag["health"] != HEALTH_COMA

        return {
            "role_diagnosis":  role_diag,
            "global_health":   global_diag,
            "risk_authorized": risk_authorized,
        }
