import pandas as pd
import numpy as np
import json
import os
import logging
from datetime import datetime

logger = logging.getLogger("ASSET_GOVERNANCE")

# Define PROJECT_ROOT
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))

class ForensicAssetAuditor:
    """
    Motor de Scoring GHI (Governance Health Index)
    Implementa: Inferencia Bayesiana, Penalización MAE y Estabilidad Sharpe-Mod.
    """
    def __init__(self, min_sample_size=12):
        self.min_sample_size = min_sample_size
        self.alpha_prior = 1 # Beta Distribution Prior
        self.beta_prior = 1
        self.max_toxic_ratio = 4.0 

    def calculate_ghi(self, symbol, trades_list):
        """
        Calcula el score de salud basado en métricas forenses.
        """
        n = len(trades_list)
        if n < self.min_sample_size:
            return {
                "symbol": symbol,
                "status": "⚪ ASPIRANTE (Testing)",
                "health_score": 50.0,
                "can_heavy": False,
                "reason": f"ASPIRANTE SIN MÉRITOS: Falta de evidencia estadística ({n}/{self.min_sample_size})"
            }

        # Extracción de métricas
        profits = np.array([t.get('profit', 0) for t in trades_list])
        # MAE Fallback: Si no existe mae_usd, asumimos el profit como MAE mínimo para pérdidas
        maes = np.array([abs(t.get('mae_usd', t.get('profit', 0) if t.get('profit', 0) < 0 else 0)) for t in trades_list])
        
        wins = profits[profits > 0]
        losses = np.abs(profits[profits < 0])
        n_wins = len(wins)

        # 1. WIN RATE BAYESIANO (P_w)
        p_w = (n_wins + self.alpha_prior) / (n + self.alpha_prior + self.beta_prior)

        # 2. RATIO DE EFICIENCIA DE RIESGO
        avg_profit = np.mean(wins) if len(wins) > 0 else 0.01
        avg_mae = np.mean(maes) if n > 0 else 1000
        risk_efficiency = avg_profit / (avg_mae + 0.001)
        
        toxic_penalty = 1.0
        if avg_mae > (avg_profit * self.max_toxic_ratio):
            toxic_penalty = 0.5
            
        # 3. PROFIT FACTOR ROBUSTO
        pf = sum(wins) / (sum(losses) + 0.01)
        pf_score = min(1.0, float(pf) / 2.0)

        # 4. ESTABILIDAD (SHARPE MODIFICADO)
        std_p = np.std(profits)
        stability = (np.mean(profits) / (std_p + 0.001)) * np.sqrt(n)

        # 5. CÁLCULO DEL GHI
        ghi = (p_w * 0.4 + pf_score * 0.4 + min(1.0, risk_efficiency) * 0.2) * 100
        ghi *= toxic_penalty

        # 6. CLASIFICACIÓN DE ESTADO (GUILOTINA)
        net_profit = np.sum(profits)
        
        status = "🔴 DESTERRADO (Toxic)"
        can_heavy = False
        reason = "TOXICIDAD FINANCIERA: Destrucción de capital detectada"

        if net_profit > 0:
            if n >= 12:
                if ghi > 65 and pf > 1.2:
                    status = "💎 ÉLITE (Heavy)"
                    can_heavy = True
                    reason = "VALOR SEGURO: Acceso total a lotaje Heavy acumulado por méritos."
                elif ghi > 55:
                    status = "🟢 HEALTHY (Normal)"
                    can_heavy = False
                    reason = "SOLIDEZ: Activo estable con derecho a lotaje estándar."
                else:
                    status = "🔴 DESTERRADO (Toxic)"
                    can_heavy = False
                    reason = "TOXICIDAD: Destrucción de capital. Bloqueo de volumen inmediato."
            else:
                if n > 0:
                    status = "⚪ ASPIRANTE (Scout)"
                    can_heavy = False
                    reason = f"TIEMPO DE PRUEBA: Falta evidencia (Sangre: {n}/12). Lote 0.01 obligatorio."
                else:
                    status = "❔ DESCONOCIDO"
                    can_heavy = False
                    reason = "SIN DATOS: No se permite operar hasta fase de recolección."
        else:
            reason = "TOXICIDAD FINANCIERA: Destrucción de capital (Exclusión Automática)"

        return {
            "symbol": symbol,
            "health_score": round(float(ghi), 1),
            "status": status,
            "can_heavy": can_heavy,
            "reason": reason,
            "profit_factor": round(float(pf), 2),
            "win_rate": round(float(n_wins / n * 100), 1),
            "total_data_points": n,
            "stability": round(float(stability), 2),
            "risk_efficiency": round(float(risk_efficiency), 2),
            "last_update": datetime.now().isoformat()
        }

class AssetHealthMonitor:
    def __init__(self, output_file="config/asset_health_report.json"):
        self.output_file = output_file
        self.auditor = ForensicAssetAuditor(min_sample_size=12)
        
    def refresh_report(self):
        """Processes trade history from the official Governance Monitor (NEME1/NEME2) and MT5."""
        history_path = os.path.join(PROJECT_ROOT, "config/health_history.json")
        
        # --- 1. Get Live Symbols from MT5 ---
        mt5_symbols = []
        try:
            import MetaTrader5 as mt5
            if not mt5.initialize():
                logger.warning("⚠️ MT5 Initialization failed in Governance Monitor.")
            else:
                symbols = mt5.symbols_get()
                mt5_symbols = [s.name for s in symbols if s.visible]
        except Exception as e:
            logger.error(f"MT5 Connection Error in Governance: {e}")

        # --- 2. Load Trade History ---
        all_trades = []
        if os.path.exists(history_path):
            try:
                with open(history_path, "r") as f:
                    data = json.load(f)
                all_trades = data.get("neme1_trades", []) + data.get("neme2_trades", [])
            except Exception as e:
                logger.error(f"Error loading health history: {e}")
        
        grouped_trades = {}
        for t in all_trades:
            sym = t.get("symbol", "UNKNOWN")
            # Normalize crypto symbols
            if sym in ["BTC", "ETH", "SOL", "XAU", "XAG"]: sym += "USD"
            
            if sym not in grouped_trades:
                grouped_trades[sym] = []
            grouped_trades[sym].append(t)

        # --- 3. Merge Source Pools ---
        portfolio_path = os.path.join(PROJECT_ROOT, "config/portfolio.json")
        port_symbols = []
        if os.path.exists(portfolio_path):
            with open(portfolio_path, "r") as f:
                port_data = json.load(f)
                port_symbols = list(port_data.get('assets', {}).keys())
        
        # Final set of symbols: Portfolio + MT5 (Active) + History
        final_symbols = sorted(list(set(port_symbols) | set(mt5_symbols) | set(grouped_trades.keys())))
        
        report = {}
        for sym in final_symbols:
            trades_for_sym = grouped_trades.get(sym, [])
            res = self.auditor.calculate_ghi(sym, trades_for_sym)
            report[sym] = res

        # Save to JSON
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        with open(self.output_file, "w") as f:
            json.dump(report, f, indent=4)
        
        return report

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    monitor = AssetHealthMonitor()
    report = monitor.refresh_report()
    
    # Visual reporting
    sorted_report = dict(sorted(report.items(), key=lambda item: item[1].get('health_score', 0), reverse=True))
    
    print("\n" + "="*90)
    print("║" + " EL SISTEMA AHORA ES UNA MERITOCRACIA ".center(88) + "║")
    print("║" + " El volumen (Heavy) se gana con sangre, sudor y estadística (12+ trades + GHI alto) ".center(88) + "║")
    print("║" + " Todo lo demás es Scout (0.01) o nada ".center(88) + "║")
    print("="*90)
    print(f"║ {'SYMBOL':<10} | {'GHI':<6} | {'PF':<5} | {'WR%':<5} | {'TRADES':<6} | {'ESTADO Y CONCLUSIÓN'} ")
    print("╟" + "─"*88 + "╢")
    for sym, data in sorted_report.items():
        print(f"║ {sym:<10} | {data.get('health_score', 0):>5}% | {data.get('profit_factor', 0):>5} | {data.get('win_rate', 0):>4}% | {data.get('total_data_points', 0):>6} | {data.get('status'):<15} ║")
        print(f"║ {' ':10}   └─> {data.get('reason')} ")
    print("═"*90)
