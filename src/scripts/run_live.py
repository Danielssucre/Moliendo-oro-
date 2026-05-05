#!/usr/bin/env python3
"""
NANOBOT LIVE TRADING RUNNER (v2.0 Clean)
- Strategy: HIVE V5 (Trend Sniper)
- ML Modules: Gatekeeper (Shadow), StopHunt (Active), RL Trailing (Active)
- Risk: Dynamic Institutional w/ Kelly Sizing
"""
import sys
import os
import logging
import time
import json
import threading
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

# --- [v6.2.2] MASTER PATH RESOLUTION ---
# Ensure the trading_agent and its src folder are always in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(current_dir))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

for p in [PROJECT_ROOT, SRC_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

# --- [V6.2.0] SURVIVAL PERSISTENCE (FTMO IRON DOME READY) ---
try:
    from nanobot.state_persistence import StatePersistence
    from nanobot.volatility_engine import VolatilityEngine
    persistence_handler = StatePersistence()
except ImportError:
    # Fallback to absolute if path hack somehow localizes different
    from src.nanobot.state_persistence import StatePersistence
    persistence_handler = StatePersistence()
    from src.nanobot.volatility_engine import VolatilityEngine

from nanobot.risk_manager import MeritocraticRiskManager

# --- GLOBAL COMPONENTS ---
vol_engine = None # Initialized in main()
risk_tribunal = None # Initialized in main()
class AlphaSignal:
    def __init__(self, symbol, direction, confidence, strategy_tag, edge_type, suggested_rr, regime):
        self.symbol, self.direction, self.confidence = symbol, direction, confidence
        self.strategy_tag, self.edge_type, self.suggested_rr, self.regime = strategy_tag, edge_type, suggested_rr, regime
        self.force_scout = False

def run_iron_funnel_arbitration(pair, data, signal_pool):
    is_volatile = any(k in pair.upper() for k in ["XAU", "XAG", "BTC", "ETH", "SOL"])
    force_scout = (is_volatile and INITIAL_CAPITAL < 100000)
    for s in signal_pool:
        if s.symbol == pair and force_scout: 
            s.force_scout = True
            logger.info(f"⚖️ [IRON FUNNEL] Signal {s.strategy_tag} on {pair} forced to SCOUT mode (0.01 lot).")
    return signal_pool

# --- [V8.5.0] SURVIVAL PROTOCOLS (ROLLOVER KILL-SWITCH) ---
def get_rollover_kill_pnl(mt5_client):
    """Calcula el PnL total de los trades cerrados por el Killswitch hoy."""
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # Scan today's deals (since 00:00 UTC)
        start_date = datetime(now.year, now.month, now.day)
        deals = mt5_client.history_deals_get(start_date, now + timedelta(hours=1))
        if not deals: return 0.0
        
        total_kill_pnl = 0.0
        for d in deals:
            if d.entry == 1: # OUT
                if "[ROLLOVER_KILL]" in getattr(d, 'comment', ''):
                    total_kill_pnl += (d.profit + d.swap + d.commission)
        return total_kill_pnl
    except Exception as e:
        logger.error(f"❌ Error calculando Rollover PnL: {e}")
        return 0.0

def check_rollover_killswitch(mt5_client, persistence_handler):
    """
    [V8.5.0] ROLLOVER KILL-SWITCH & BUNKER
    Controla la liquidación de emergencia a las 23:55 y el bloqueo de hibernación.
    """
    try:
        # 1. Obtener hora del servidor (Reloj de FTMO)
        tick = mt5_client.symbol_info_tick("EURUSD")
        if tick:
            server_time = datetime.fromtimestamp(tick.time)
        else:
            # Fallback a UTC+2 (Standard FTMO/EET)
            server_time = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=2)
            
        hour = server_time.hour
        minute = server_time.minute
        
        state = persistence_handler.state
        lock_active = state.get("rollover_lock", False)
        
        # --- [GATILLO 1: LA LIQUIDACIÓN (23:55) DISABLED] ---
        # Omega Core requiere que cada trade toque su TP/SL natural.
        if False: # hour == 23 and minute >= 55:
            if not lock_active:
                logger.warning(f"⚠️ [ROLLOVER KILL-SWITCH] Hora servidor: {server_time.strftime('%H:%M:%S')}. Iniciando Búnker.")
                positions = mt5_client.positions_get()
                if positions:
                    for pos in positions:
                        # Solo cerrar si NO está en Breakeven positivo (PnL < 0)
                        if pos.profit + pos.swap + pos.commission < 0:
                            logger.info(f"💀 [KILL] Liquidando {pos.symbol} #{pos.ticket}")
                            mt5_client.eval(f"mt5.Close('{pos.symbol}', ticket={pos.ticket}, comment='[ROLLOVER_KILL]')")
                
                state["rollover_lock"] = True
                persistence_handler.save()
                logger.info("🔒 [BÚNKER ACTIVADO] Hibernación total hasta las 02:00 AM.")
            return True
            
        # --- [GATILLO 2: EL AMANECER (02:00)] ---
        if hour >= 2 and hour < 23:
            if lock_active:
                state["rollover_lock"] = False
                persistence_handler.save()
                logger.info("☀️ [BÚNKER DESACTIVADO] Mercado en horario líquido. Radares activos.")
            return False
            
        return lock_active
        
    except Exception as e:
        logger.error(f"❌ Error en Rollover Kill-Switch: {e}")
        return persistence_handler.state.get("rollover_lock", False)

def harvest_reversal_data(positions, mt5_client, persistence_handler):
    """
    [Fase 4: Shadow Harvester]
    Analiza la canasta activa antes del cierre para identificar la 'Zona de Reversión' (Pivot).
    Calcula la distancia en ATR desde L1 hasta el nivel más profundo alcanzado.
    """
    try:
        if not positions: return
        
        # Agrupar por símbolo
        by_symbol = {}
        for p in positions:
            if p.symbol not in by_symbol: by_symbol[p.symbol] = []
            by_symbol[p.symbol].append(p)
            
        for symbol, pos_list in by_symbol.items():
            # Solo procesar si hay al menos una orden de MegaGrid
            grid_positions = [p for p in pos_list if "_L" in getattr(p, 'comment', '')]
            if not grid_positions: continue
            
            l1_pos = None
            pivot_pos = None
            max_level = 0
            
            for p in grid_positions:
                comment = getattr(p, 'comment', '')
                try:
                    # Formato esperado: ..._L1_...
                    if "_L" in comment:
                        parts = comment.split("_L")
                        if len(parts) > 1 and parts[1][0].isdigit():
                            level = int(parts[1][0])
                            if level == 1: l1_pos = p
                            if level > max_level:
                                max_level = level
                                pivot_pos = p
                except: continue
            
            if l1_pos and pivot_pos and vol_engine:
                atr = vol_engine.get_symbol_atr(symbol)
                if atr and atr > 0:
                    dist_price = abs(pivot_pos.price_open - l1_pos.price_open)
                    dist_atr = dist_price / atr
                    
                    if dist_atr >= 0:
                        logger.info(f"📊 [SHADOW HARVEST] {symbol} Reversión en L{max_level} (Distancia: {dist_atr:.2f} ATR)")
                        persistence_handler.update_reversal_profile(symbol, dist_atr)
                        
    except Exception as e:
        logger.error(f"❌ Error en Shadow Harvester: {e}")

class MegaGridTracker:
    def __init__(self, mt5_client, logger):
        self.client, self.logger = mt5_client, logger
        
    def execute_signal(self, signal, risk_pct=None):
        from nanobot.strategies.mega_grid_v2 import MegaGridV2
        global RISK_PER_TRADE, current_capital, ASSET_MAP
        
        pair = signal.symbol
        # 1. DETERMINAR ROL (NEM1/NEM2) - INTELIGENCIA BAYESIANA ACTIVA
        pair_settings = _last_tactical_config.get(pair, {"strategy_mode": "AUTO"})
        strat_mode = pair_settings.get("strategy_mode", "AUTO")
        
        # Default basado en dirección (Tesis Original)
        nem_type = "NEM1" if signal.direction == 1 else "NEM2"
        
        # Cargar Inteligencia del Mapa de Calor
        try:
            with open(AFFINITY_MAP_PATH, "r") as f:
                affinity_data = json.load(f)
                asset_intel = affinity_data.get(pair, {})
                ai_reco = asset_intel.get("reco", "") # "NEM1 (Trend)" o "NEM2 (Antith)"
                
                if strat_mode == "AUTO" and ai_reco:
                    nem_type = "NEM1" if "NEM1" in ai_reco else "NEM2"
                    self.logger.info(f"🧠 [AUTO-SWITCH] IA ha catalogado {pair} como {nem_type}. Aplicando rol dinámico.")
        except:
            pass

        if strat_mode == "MANUAL":
            nem_type = pair_settings.get("manual_nem_role", nem_type)
            self.logger.warning(f"🎯 [DASHBOARD OVERRIDE] Usando Rol manual: {nem_type} para {pair}")

        # 2. INICIALIZAR ESTRATEGIA Y DATOS
        strategy = MegaGridV2()
        symbol_mt5 = ASSET_MAP.get(pair, pair)
        
        data = get_mt5_data(symbol_mt5, bars=100)
        if not data.empty:
            atr_series = calculate_atr(data)
            atr_val = float(atr_series.iloc[-2]) if len(atr_series) > 2 else 0.00100
        else:
            atr_val = 0.00100
            
        # 3. GENERAR POOL DE PRECISIÓN (Masa Pesada OMEGA+)
        tick = self.client.symbol_info_tick(symbol_mt5)
        
        # [v7.0.0] FIX GEOMETRÍA: NEME Bug de Doble Inversión
        # La dirección enviada por StrategyHub (signal.direction) es SAGRADA.
        final_side = signal.direction
        entry_price = tick.ask if final_side == 1 else tick.bid
        
        is_scout_mode = getattr(signal, 'force_scout', False)
        
        # [Fase 4] Inyección de Inteligencia de Reversión (Gravity Well)
        reversal_data = persistence_handler.state.get("reversal_profile", {})
        
        effective_risk = risk_pct if risk_pct is not None else RISK_PER_TRADE

        # [v10.0.0] OMEGA CORE: Obtener distribución asimétrica por nivel si está disponible
        level_risks_usd = getattr(signal, '_omega_level_risks', None)
        acc_info = self.client.account_info()
        account_equity = float(acc_info.equity) if acc_info else None

        levels = strategy.generate_pool(
            symbol=symbol_mt5, entry_price=entry_price, atr=atr_val,
            direction=final_side, total_risk=effective_risk, 
            is_scout=is_scout_mode, nem_type=nem_type,
            reversal_profile=reversal_data,
            level_risks_usd=level_risks_usd,   # [v10.0.0] Omega Core
            account_equity=account_equity       # [v10.0.0] Para conversión USD→%
        )

        # 4. [SCOUT FIRST] DESPACHO DEL ESPÍA CON BALÍSTICA HEREDADA (L1 DNA)
        if levels:
            symbol_info = self.client.symbol_info(symbol_mt5)
            point = symbol_info.point if symbol_info else 0.00001
            
            l1 = levels[0]
            # [v6.7.0] El Scout es el ESPÍA del lado contrario a la Heavy.
            # Si la Heavy es NEM1 (Trend), el Scout es NEM2 (Antith).
            # Si el lado de la Heavy es 1 (BUY), el Scout debe ser SELL (-1).
            spy_side = -1 * l1['side']
            spy_dir = "BUY" if spy_side == 1 else "SELL"
            spy_role = "NEM1" if nem_type == "NEM2" else "NEM2"
            
            sl_dist = atr_val * l1['sl_mult']
            # Safety Fallback: Min 10 points
            if sl_dist < point * 10: sl_dist = point * 30 
            
            tp_dist = sl_dist * l1['rr']
            
            spy_entry = tick.ask if spy_dir == "BUY" else tick.bid
            if spy_dir == "BUY":
                spy_sl = spy_entry - sl_dist
                spy_tp = spy_entry + tp_dist
            else:
                spy_sl = spy_entry + sl_dist
                spy_tp = spy_entry - tp_dist
                
            # [v6.3.2] BLACK-BOX RISK ADN: Inyectar riesgo original en puntos para el Harvester
            risk_points = int(sl_dist / point) if point > 0 else 0
            # [v10.2] MT5 RPyC LIMIT: max 20 chars total including VSL
            _role_s = "N1" if "NEM1" in spy_role else "N2"
            spy_comment = f"S_L1_{_role_s}" # 7 chars
            
            self.logger.info(f"🕵️ [SCOUT FIRST] Desplegando sonda HEREDERA ({spy_role}): {pair} {spy_dir} | SL_Pts: {risk_points}")
            execute_mt5_trade(symbol_mt5, spy_dir, spy_entry, spy_sl, spy_tp, 0.01, comment=spy_comment)
            time.sleep(0.5)

        # 5. EJECUCIÓN ATÓMICA DE LA RED HEAVY
        self.logger.info(f"🚀 [MEGAGRID DISPATCH] Desplegando {len(levels)} niveles para {pair} en modo {nem_type}")
        
        for level in levels:
            nem_side = level['side']
            side_str = "BUY" if nem_side == 1 else "SELL" # TRADUCCIÓN CORRECTA
            
            sl_dist = atr_val * level['sl_mult']
            tp_dist = sl_dist * level['rr']
            
            if nem_side == 1: # BUY
                sl_price = level['entry'] - sl_dist
                tp_price = level['entry'] + tp_dist
            else: # SELL
                sl_price = level['entry'] + sl_dist
                tp_price = level['entry'] - tp_dist
                
            risk_usd = current_capital * level['risk_pct']
            symbol_info = self.client.symbol_info(symbol_mt5)
            point = symbol_info.point if symbol_info else 0.0001
            sl_pips = sl_dist / (point * 10) if point < 0.01 else sl_dist / point
            sl_pips = max(1.0, sl_pips)
            
            lot_size = (risk_usd / (sl_pips * 10))
            lot_size = max(0.01, round(lot_size, 2))

            # --- [v6.8.7] PURE VS PURE (DNA SYNC) ---
            # En inyecciones Heavy, aislaremos el Nivel 1 (La Bala Trazadora Primaria) 
            # de su red de mitigación para poder comparar R-Multiples puros contra el Scout del bando contrario.
            if level['level'] == 1 and not is_scout_mode:
                risk_points = int(sl_dist / point) if point > 0 else 0
                _role_s = "N1" if "NEM1" in nem_type else "N2"
                comment = f"H_L1_{_role_s}" # 7 chars
            else:
                _role_s = "N1" if "NEM1" in nem_type else "N2"
                _sh = 'S' if is_scout_mode else 'H'
                comment = f"{_sh}_L{level['level']}_{_role_s}" # 7 chars
            
            trade_dir = "BUY" if nem_side == 1 else "SELL"
            execute_mt5_trade(symbol_mt5, trade_dir, level['entry'], sl_price, tp_price, lot_size, comment=comment)
            time.sleep(1.0)

# Silenciador de Telemetría (v4.5.0)
LAST_TELEGRAM_ERROR_TIME = 0
TELEGRAM_ERROR_COOLDOWN = 60 

# --- [v6.3.2] AFFINITY HARVESTER INFRASTRUCTURE ---
AFFINITY_MAP_PATH = "data/research/affinity_map.json"

def affinity_harvester_daemon(mt5_client, logger):
    """
    COSECHADOR ASÍNCRONO: Procesa trades cerrados de Scouts para medir la Afinidad Bayesiana.
    """
    logger.info("🛰️ AFFINITY HARVESTER: Intelligence gathering thread online.")
    os.makedirs(os.path.dirname(AFFINITY_MAP_PATH), exist_ok=True)
    
    # [v6.4.0] FAST-TRACK INITIALIZATION
    first_run = True
    
    while True:
        try:
            # 1. Ciclo táctico: 10s al inicio, 900s después
            sleep_time = 10 if first_run else 900
            time.sleep(sleep_time) 
            first_run = False
            
            # 2. Intento de adquisición NO BLOQUEANTE del Puente
            global _execution_lock
            if not _execution_lock.acquire(blocking=False):
                continue
                
            try:
                from_date = datetime.now() - timedelta(days=7) # Ver 7 días para data inicial
                history_deals = mt5_client.history_deals_get(from_date, datetime.now())
                
                if not history_deals:
                    continue
                    
                # [v7.5.2] Mapeo de Position ID -> Original Comment (Anti SL/TP overwrite)
                pos_to_comment = {}
                for deal in history_deals:
                    if getattr(deal, 'entry', 0) == 0: # Entry IN
                        pos_to_comment[deal.position_id] = getattr(deal, 'comment', "")
                    
                # Cargar mapa actual
                map_data = {}
                if os.path.exists(AFFINITY_MAP_PATH):
                    try:
                        with open(AFFINITY_MAP_PATH, "r") as f: map_data = json.load(f)
                    except: pass
                
                changes = False
                for deal in history_deals:
                    # Solo procesar trades cerrados (entry out)
                    if getattr(deal, 'entry', 0) != 1: continue 
                    
                    # Recuperar comentario original (evita pérdida por SL/TP overwrite)
                    comment = pos_to_comment.get(deal.position_id, getattr(deal, 'comment', ""))
                    ticket = str(deal.ticket)
                    
                    # [v10.2] GRANULAR HARVESTER: Detectar cualquier nivel L1-L7
                    import re as _re
                    # Soporta formato legacy (L1_SCOUT_, _L1_) y ultra-short (S_L1_N1, H_L2_N2)
                    level_match = _re.search(r'_L(\d)(?:_|$)', comment)
                    # Scout: formato legacy 'L1_SCOUT' o ultra-short 'S_' prefix
                    is_scout = ("L1_SCOUT" in comment) or comment.startswith("S_")
                    # Heavy grid: tiene nivel _Ln_ y no es scout
                    is_grid_level = level_match is not None
                    
                    if not (is_scout or is_grid_level): continue
                    
                    pair = deal.symbol
                    if pair not in map_data: map_data[pair] = {}
                    
                    # Determinar Rol (soporta legacy y ultra-short _N1/_N2)
                    role = "NEM1"  # default
                    if "_NEM2" in comment or "_N2" in comment: role = "NEM2"
                    elif "_NEM1" in comment or "_N1" in comment: role = "NEM1"
                    
                    # [v10.0.0] Extraer nivel granular (L1..L7)
                    level_num = int(level_match.group(1)) if level_match else 1
                    level_key = f"L{level_num}"
                    
                    if role not in map_data[pair]: map_data[pair][role] = {"n": 0, "sum_r": 0.0, "tickets": []}
                    
                    if ticket not in map_data[pair][role]["tickets"]:
                        total_profit = deal.profit + deal.swap + deal.commission
                        
                        # Proxy R-Multiple: (+1 Win, -1 Loss) para compatibilidad legacy
                        r_realized = 1.0 if total_profit > 0 else -1.0 
                        
                        map_data[pair][role]["n"] += 1
                        map_data[pair][role]["sum_r"] += r_realized
                        map_data[pair][role]["tickets"].append(ticket)
                        
                        # [v10.0.0] MEMORIA GRANULAR POR NIVEL (L1-L7)
                        # Guardamos el beneficio REAL en USD para calcular WR y PF clínico
                        if "levels" not in map_data[pair][role]:
                            map_data[pair][role]["levels"] = {}
                        if level_key not in map_data[pair][role]["levels"]:
                            map_data[pair][role]["levels"][level_key] = {"n": 0, "wins": 0, "profit_history": [], "tickets": []}
                        
                        level_data = map_data[pair][role]["levels"][level_key]
                        if ticket not in level_data["tickets"]:
                            level_data["n"] += 1
                            if total_profit > 0:
                                level_data["wins"] += 1
                            level_data["profit_history"].append(round(total_profit, 4))
                            level_data["tickets"].append(ticket)
                            # Ventana deslizante de 50 operaciones por nivel
                            if len(level_data["profit_history"]) > 50:
                                level_data["profit_history"] = level_data["profit_history"][-50:]
                            if len(level_data["tickets"]) > 50:
                                level_data["tickets"] = level_data["tickets"][-50:]
                        
                        # [v9.0.0] Intelligence Expansion: Tensor 3D (Hour of Day)
                        dt = datetime.fromtimestamp(deal.time)
                        hour_key = str(dt.hour)
                        if "hourly" not in map_data[pair][role]:
                            map_data[pair][role]["hourly"] = {str(h): {"n": 0, "sum_r": 0.0} for h in range(24)}
                        
                        map_data[pair][role]["hourly"][hour_key]["n"] += 1
                        map_data[pair][role]["hourly"][hour_key]["sum_r"] += r_realized

                        if len(map_data[pair][role]["tickets"]) > 200:
                            map_data[pair][role]["tickets"] = map_data[pair][role]["tickets"][-200:]
                        changes = True
                        logger.debug(f"🔬 [GRANULAR HARVEST] {pair}/{role}/{level_key} | Profit: ${total_profit:.4f} | Total muestras: {level_data['n']}")
                
                if changes:
                    # [v6.4.0] AUTO-CATALOGING LOGIC
                    for p in map_data:
                        n1 = map_data[p].get("NEM1", {"sum_r": 0})["sum_r"]
                        n2 = map_data[p].get("NEM2", {"sum_r": 0})["sum_r"]
                        map_data[p]["reco"] = "NEM1 (Trend)" if n1 >= n2 else "NEM2 (Antith)"
                    
                    # [v6.6.2] ATOMIC RESILIENT SAVE
                    from nanobot.utils.database import SecureDatabaseManager as db
                    db.save_json(AFFINITY_MAP_PATH, map_data)
                    logger.info(f"🛰️ AFFINITY MAP: Intelligence updated and secured. {len(map_data)} assets cataloged.")
                    
            finally:
                _execution_lock.release()
                
        except Exception as e:
            logger.error(f"❌ Harvester Error: {e}")

# --- GLOBAL STATE (MEGAGRID & LOCKING) ---
mega_grid_tracker = None
_execution_lock = threading.Lock()

# --- ALPHA SUPREMO HUB INFRASTRUCTURE (GLOBAL SCOPE) ---

# Initialize StrategyHub early
try:
    from nanobot.strategies.strategy_hub import StrategyHub
    STRATEGY_HUB = StrategyHub()
    STRATEGY_HUB_ENABLED = True
    print("✅ STRATEGY HUB (ForexInfantry + CryptoLab) initialized")
except Exception as e:
    print(f"❌ STRATEGY HUB init failed: {e}")
    STRATEGY_HUB = None
    STRATEGY_HUB_ENABLED = False

import threading
from datetime import datetime, timedelta, timezone

# --- LOGGING SETUP ---
try:
    from nanobot.utils.telegram_bot import TelegramBot
except ImportError:
    class TelegramBot: # Fallback dummy
        enabled = False
        def send_message(self, msg): print(f"TELEGRAM MOCK: {msg}")
        def send_basket_report(self, *a, **k): print(f"TELEGRAM MOCK: Basket Report")

from nanobot.ml.stop_hunt import StopHuntModel
ML_ENABLED = True

try:
    from nanobot.strategies.skypie_enel import SkypieEnel
    ENEL_ENGINE = SkypieEnel()
    ENEL_ENABLED = True
except ImportError:
    ENEL_ENABLED = False
    print("⚠️ Skypie-Enel strategy module not found.")

try:
    from nanobot.strategies.hunter_x import HunterX
    HUNTER_X_ENGINE = HunterX()
    HUNTER_X_ENABLED = True
except ImportError:
    HUNTER_X_ENABLED = False
    print("⚠️ Hunter X strategy module not found.")

try:
    from nanobot.kelly_sizing import BayesianEnsemble as BayesianBeliefEngine
    BAYES_ENABLED = True
except ImportError:
    try:
        from nanobot.kelly_sizing import KellyBeliefEngine
        BAYES_ENABLED = True
    except:
        BAYES_ENABLED = False
        print("⚠️ Kelly Module missing.")

try:
    # [v10.2] RL Trailing DISABLED: Omega Core requiere pureza estadística (esperar a TP/SL)
    RL_AGENT_ENABLED = False
    class RLTrailingManager: pass  # Stub
except Exception as e:
    RL_AGENT_ENABLED = False
    class RLTrailingManager: pass  # Stub

try:
    # [v10.2] MFE Sniper DISABLED: Omega Core requiere pureza estadística (esperar a TP/SL)
    SNIPER_ENABLED = False
    class MFESniperManager: pass # Stub
except Exception as e:
    SNIPER_ENABLED = False
    class MFESniperManager: pass # Stub

try:
    from nanobot.ml.risk_oracle import AsymmetricRiskOracle
    RISK_ORACLE_ENABLED = True
except Exception as e:
    RISK_ORACLE_ENABLED = False
    print(f"⚠️ Risk Oracle disabled: {e}")
    class AsymmetricRiskOracle: pass  # Stub

try:
    from nanobot.orchestrator import BotOrchestrator
    ORCHESTRATOR_ENABLED = True
except Exception as e:
    ORCHESTRATOR_ENABLED = False
    print(f"⚠️ All-Weather Orchestrator disabled: {e}")
    class BotOrchestrator:  # Stub
        def __init__(self, *a, **kw): pass
        def evaluate(self, *a, **kw): return {"regime": "TREND", "allow_hive": True, "mr_signal": None, "sh_signals": [], "protect_tickets": [], "reason": "stub"}
        def status_report(self): return "Orchestrator: STUB"

orchestrator = None  # Inicializado tras conexión MT5

# --- POLIMATA LIVE RL (Master of Chameleon) ---
try:
    from stable_baselines3 import DQN
    import gymnasium as gym
    POLIMATA_MODEL_PATH = "models/polimata_rl_v1.zip"
    if os.path.exists(POLIMATA_MODEL_PATH):
        polimata_model = DQN.load(POLIMATA_MODEL_PATH)
        POLIMATA_ENABLED = True
        print("🧠 POLIMATA RL: Online and Loaded.")
    else:
        polimata_model = None
        POLIMATA_ENABLED = False
except Exception as e:
    POLIMATA_ENABLED = False
    polimata_model = None
    print(f"⚠️ Polimata RL disabled: {e}")

# --- META-RL SELECTOR (3 Strategy Experiment) ---
try:
    from nanobot.ml.meta_rl_selector import MetaRLSelector
    META_SELECTOR_ENABLED = True
except Exception as e:
    META_SELECTOR_ENABLED = False
    print(f"⚠️ Meta-RL Selector disabled: {e}")

meta_selector = None  # Inicializado en main()

# --- TELEGRAM BOT (Global) ---
bot = TelegramBot()

# --- LOGGING SETUP ---
log_dir = "logs"
if not os.path.exists(log_dir): os.makedirs(log_dir)
log_file = os.path.join(log_dir, f"trading_{datetime.now().strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("NAANOBOT_FTMO")

# --- BASKET LOCK TRACKING (Visual Proof for User) ---
LAST_BASKET_ENABLED = None
LAST_BASKET_THRESHOLD = None
LAST_BASKET_RELEASE_TIME = 0
GLOBAL_RESUME_TIME = 0 # Global timestamp for cooldown

def load_tactical_config():
    """
    Lectura Segura del Puente Dashboard y Configuración de Riesgo (v4.1.5).
    Implementa un sensor dual para activos y parámetros globales.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    bridge_path = os.path.join(project_root, "config", "dashboard_bridge.json")
    config_path = os.path.join(project_root, "config", "trading_config.json")
    
    tactical = {}
    global_risk = 0.004 # Fallback Institucional

    # 1. Leer Estado de Activos (Bridge 8080)
    if os.path.exists(bridge_path):
        try:
            with open(bridge_path, 'r') as f:
                tactical = json.load(f)
        except: pass

    # 2. Leer Riesgo Maestro (Config 8000) - SINCRO DINÁMICA CON TRUST TIERS
    try:
        # El riesgo ya no es estático del JSON, sino dinámico según el progreso del Bot
        global_risk = persistence_handler.get_trust_risk_pct()
    except Exception as e:
        global_risk = 0.0015 # Safe Fallback (Tier 1)

    return tactical, global_risk
CURRENT_BASKET_PEAK = 0.0    # Trailing peak tracking
CURRENT_BASKET_FLOOR = -999.0 # Safety floor

# --- VIRTUAL ORDER MANAGER (SHADOW GRID) ---
print("DEBUG: L125 - GLOBAL SCOPE PROGRESSING")
# --- REAL GRID MANAGER (L-H-N REAL EXPERIMENT) ---
class RealGridManager:
    """Manages 40 real trades per signal (Thesis/Antithesis) to track real-market outcomes."""
    def __init__(self, log_file="data/research/shadow_grid_results.csv"):
        self.log_file = log_file
        self.active_trades = [] # List of dicts with {ticket, symbol, config, etc.}
        self._ensure_log_exists()
        self.critical_errors_detected = 0 # Phase 98 Safety

    def _ensure_log_exists(self):
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w") as f:
                f.write("time,symbol,config,prob,adx,rsi,vol,outcome_r,mfe_r,mae_r,session,ticket,entry_real,exit_real\n")

    def _get_session(self):
        """Identify current trading session (UTC)."""
        hour = datetime.now(timezone.utc).hour
        if 0 <= hour < 8: return "ASIA"
        if 8 <= hour < 13: return "LONDON"
        if 13 <= hour < 21: return "NY"
        return "SYDNEY"

    def register_signal_pool(self, symbol, entry_price, current_atr, adx_val, rsi_val, vol_val, prob_val, sig, dist_ema200=0.0, source="LHN"):
        """Execute Optimized real variants for a single signal using the L-H-N Beta Hypothesis (25/25/25/25)."""
        session = self._get_session()
        is_master = (source == "LHN")
        configs_to_run = []
        
        # 25% ALFA (Trend Sniper)
        for rr in [1.5, 1.8, 2.0, 2.5]:
            for slm in [1.5, 2.0]: 
                configs_to_run.append({'rr': rr, 'sl_mult': slm, 'side': 1, 'tag': 'ALFA'})
        
        # 25% WINNER (Optimized 1.5R - Data Driven)
        for slm in [1.0, 1.2, 1.5, 1.8, 2.0, 2.5, 3.0, 4.0]:
            configs_to_run.append({'rr': 1.5, 'sl_mult': slm, 'side': 1, 'tag': 'WINNER'})
            
        # 25% EXPL (Trend Runner)
        for rr in [3.0, 4.0, 5.0, 8.0]:
            for slm in [1.5, 2.5]:
                configs_to_run.append({'rr': rr, 'sl_mult': slm, 'side': 1, 'tag': 'EXPL'})
                
        # 25% NEME (Antithesis - Mean Reversion)
        for rr in [1.0, 1.2, 1.5, 2.0]:
            for slm in [1.5, 2.0]:
                configs_to_run.append({'rr': rr, 'sl_mult': slm, 'side': -1, 'tag': 'NEME'})

        # Limit to 40 variants total for MASTER to avoid 10040 bottleneck
        # For experimental Lab 2.0 signals, limit to 8 variants (2 per block)
        if is_master:
            configs_to_run = configs_to_run[:20]
        else:
            # Pick 2 of each
            final_lab = []
            for tag in ['ALFA', 'WINNER', 'EXPL', 'NEME']:
                matches = [c for c in configs_to_run if c['tag'] == tag]
                final_lab.extend(matches[:2])
            configs_to_run = final_lab

        count = 0
        for cfg in configs_to_run:
            config_name = f"{cfg['tag']}_S{int(cfg['sl_mult']*10)}R{int(cfg['rr']*10)}_{'N' if cfg['side']==1 else 'I'}"
            actual_sig = sig if cfg['side'] == 1 else -sig
            
            sl_dist = float(current_atr) * float(cfg['sl_mult'])
            if sl_dist <= 0: sl_dist = 0.0001
            tp_dist = sl_dist * float(cfg['rr'])
            
            sl = float(entry_price) - sl_dist if actual_sig == 1 else float(entry_price) + sl_dist
            tp = float(entry_price) + tp_dist if actual_sig == 1 else float(entry_price) - tp_dist
            
            order_type = "BS (Buy Stop)" if actual_sig == 1 else "SS (Sell Stop)"
            
            # Lot size adjusted: 0.01 for Standard, 0.03 for Némesis (Triple Antithesis)
            lot_to_use = 0.03 if cfg['tag'] == 'NEME' else 0.01
            res = execute_mt5_trade(symbol, order_type, float(entry_price), sl, tp, lot_to_use, comment=f"{source}_{config_name}")
            
            if res:
                if res.retcode == 10009:
                    count += 1
                    self.active_trades.append({
                        "ticket": res.order,
                        "symbol": symbol,
                        "config": config_name,
                        "entry": res.price,
                        "sl": sl,
                        "tp": tp,
                        "sig": actual_sig,
                        "prob": prob_val,
                        "adx": adx_val,
                        "rsi": rsi_val,
                        "vol": vol_val,
                        "rr": cfg['rr'],
                        "sl_dist": sl_dist,
                        "peak_r": 0.0,
                        "drawdown_r": 0.0,
                        "session": session
                    })
                elif res.retcode in [10027, 10012, 10014, 10017, 10018]:
                    # 10027: AutoTrading Disabled, 10018: Market Closed, etc.
                    logger.error(f"🛑 CRITICAL BROKER ERROR ({res.retcode}): {res.comment}. Aborting variant pool for {symbol}.")
                    self.critical_errors_detected += 1
                    break # STOP trying other variants for this signal
                    
                time.sleep(0.01)

        is_death_zone = abs(dist_ema200) < 0.02
        logger.info(f"📡 [{source}] Executed {count}/{len(configs_to_run)} variations for {symbol} | Ses: {session} | DeathZone: {is_death_zone}")

    def update(self):
        """Monitor active real trades via MT5 history and track peaks."""
        if not MT5_CONNECTED: return
        
        closed_indices = []
        for i, trade in enumerate(self.active_trades):
            ticket = trade['ticket']
            # Check if ticket is still an active position
            pos = mt5_client.positions_get(ticket=ticket)
            orders = mt5_client.orders_get(ticket=ticket)
            
            if pos:
                p = pos[0]
                # Calculate current R
                current_profit = p.profit
                # R = (CurrentPrice - Entry) / (Entry - SL)
                sl_dist = trade['sl_dist']
                if sl_dist > 0:
                    curr_price = p.price_current
                    curr_r = (curr_price - trade['entry']) / sl_dist if trade['sig'] == 1 else (trade['entry'] - curr_price) / sl_dist
                    trade['peak_r'] = max(trade['peak_r'], curr_r)
                    trade['drawdown_r'] = min(trade['drawdown_r'], curr_r)
                continue

            if not orders:
                # Ticket is neither an active order nor a position -> It's closed (or cancelled)
                outcome_r, exit_price = self._get_ticket_outcome(ticket, trade['entry'], trade['sl'], trade['tp'], trade['sig'], trade['rr'])
                if outcome_r is not None:
                    self._log_result(trade, outcome_r, exit_price)
                closed_indices.append(i)
                
        # Remove closed trades from memory tracker
        for index in sorted(closed_indices, reverse=True):
            self.active_trades.pop(index)

    def _get_ticket_outcome(self, ticket, entry, sl, tp, sig, rr):
        """Fetch real outcome from MT5 history."""
        # Look back 24h for history
        from_date = datetime.now() - timedelta(days=1)
        deals = mt5_client.history_deals_get(ticket=ticket)
        if not deals:
            history = mt5_client.history_orders_get(ticket=ticket)
            if history and history[0].state == mt5_client.ORDER_STATE_CANCELED:
                return -0.05, 0 
            return None, 0

        # Find the exit price from the last deal
        exit_p = deals[-1].price
        # Calculate realized R based on entry/sl distance
        sl_dist = abs(entry - sl)
        if sl_dist == 0: return 0, exit_p
        
        realized_r = (exit_p - entry) / sl_dist if sig == 1 else (entry - exit_p) / sl_dist
        return realized_r, exit_p

    def _log_result(self, trade, outcome_r, exit_real):
        """Save real result to CSV with MFE/MAE."""
        try:
            with open(self.log_file, "a") as f:
                f.write(f"{datetime.now().isoformat()},{trade['symbol']},{trade['config']},"
                        f"{trade['prob']},{trade['adx']},{trade['rsi']},{trade['vol']},"
                        f"{outcome_r:.4f},{trade['peak_r']:.4f},{trade['drawdown_r']:.4f},{trade['session']},"
                        f"{trade['ticket']},{trade['entry']:.5f},{exit_real:.5f}\n")
            status = "WIN" if outcome_r > 0 else "LOSS"
            logger.info(f"📊 [LHN-REAL] {trade['symbol']} {trade['config']} {status} (R:{outcome_r:.2f}, MFE:{trade['peak_r']:.2f}, Session:{trade['session']})")
        except Exception as e:
            logger.error(f"❌ Error logging real result: {e}")

virtual_manager = RealGridManager()

import argparse

# --- ARGS ---
parser = argparse.ArgumentParser(description='Nanobot Live Runner v2.1 (Optimized)')
parser.add_argument('--capital', type=float, default=10000, help='Account Balance')
parser.add_argument('--creds', type=str, default='config/credentials.json', help='Credentials path')
args = parser.parse_args()

# --- CONFIGURATION ---
INITIAL_CAPITAL = args.capital
DEFAULT_CREDS_PATH = args.creds
current_capital = INITIAL_CAPITAL # Default fallback

# Risk Management (Updated Phase 45: "Fast FTMO")
RISK_PER_TRADE = 0.004 # 0.4% (Scientific Sweet Spot)
MAX_EXPOSURE_PCT = 0.05   # 5% max risk across all open trades
MAX_TRADES_PER_PAIR = 60 # Adjusted to match optimized grid 

# --- SILICON MT5 INTEGRATION (Phase 70) 🍏 ---
# --- SILICON MT5 INTEGRATION (Phase 70) 🍏 ---
MT5_CONNECTED = False
mt5_client = None

class MT5ConnectionManager:
    """
    Robust Connection Handler for Silicon MT5.
    Implements exponential backoff and continuous health checks.
    """
    def __init__(self, port=18812):
        self.port = port
        self.client = None
        self.connected = False
        self.creds = self._load_creds()
        
    def _load_creds(self):
        """Loads account credentials if they exist."""
        try:
            creds_path = DEFAULT_CREDS_PATH
            if os.path.exists(creds_path):
                with open(creds_path, 'r') as f:
                    data = json.load(f)
                    return data.get("mt5")
        except Exception as e:
            print(f"⚠️ Could not load Credentials: {e}")
        return None

    def connect(self, max_retries=5):
        global MT5_CONNECTED, mt5_client
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                from siliconmetatrader5 import MetaTrader5
                self.client = MetaTrader5(port=self.port)
                
                print(f"📡 BUSCANDO TERMINAL MT5 (Intento {attempt+1}/{max_retries})...")
                
                # Handshake Base: Intenta engancharse al terminal abierto
                if not self.client.initialize():
                    print(f"❌ No se detectó terminal MT5 abierto: {self.client.last_error()}")
                else:
                    # Lógica de Acoplamiento Automático / Manual
                    login_info = self.creds or {}
                    c_login = int(login_info.get("account", 0))
                    c_pass = login_info.get("password", "")
                    c_server = login_info.get("server", "")

                    if c_login and c_pass:
                        # LOGIN MANUAL: Si hay credenciales completas, intentamos login
                        print(f"🔐 Intentando Login Manual: #{c_login} en {c_server}")
                        authorized = self.client.login(login=c_login, password=c_pass, server=c_server)
                        if authorized:
                            self.connected = True
                            print(f"✅ Login Manual Exitoso")
                    else:
                        # ACOPLAMIENTO AUTOMÁTICO: Usar sesión activa en el terminal
                        acc_info = self.client.account_info()
                        if acc_info:
                            self.connected = True
                            print(f"🔗 ACOPLAMIENTO AUTOMÁTICO: Detectada cuenta #{acc_info.login} ({acc_info.server})")
                        else:
                            print("⚠️ Terminal detectado pero no hay cuenta activa. Inicie sesión en MT5.")

                if self.connected:
                    MT5_CONNECTED = True
                    mt5_client = self.client
                    acc = self.client.account_info()
                    print(f"🍏 SISTEMA OPERATIVO: Cuenta #{acc.login} | Balance: ${acc.balance:,.2f}")
                    
                    # [NEW v4.5.1] PROACTIVE HEALTH CHECK
                    terminal = self.client.terminal_info()
                    if terminal and not terminal.trade_allowed:
                        warn_msg = "⚠️ ALERTA: AlgoTrading DESACTIVADO en MT5. El bot NO podrá ejecutar trades."
                        print(warn_msg)
                        if 'bot' in globals() and bot.enabled:
                            bot.send_message(warn_msg)
                            
                    return True

            except Exception as e:
                print(f"⚠️ Error de Conexión: {e}")
                
            time.sleep(retry_delay)
            retry_delay *= 2
            
        return False

    def close_all_positions(self):
        """Emergency closure of all open positions."""
        if not self.client: return
        try:
            positions = self.client.positions_get()
            if not positions:
                print("✅ No active positions to close.")
                return
            
            for p in positions:
                symbol = p.symbol
                ticket = p.ticket
                qty = p.volume
                side = 1 if p.type == 0 else 0 
                
                request = {
                    "action": int(self.client.TRADE_ACTION_DEAL),
                    "symbol": str(symbol),
                    "volume": float(qty),
                    "type": int(side),
                    "position": int(ticket),
                    "price": float(self.client.symbol_info_tick(symbol).bid if side == 1 else self.client.symbol_info_tick(symbol).ask),
                    "deviation": 20,
                    "magic": 99999,
                    "comment": "Emergency Closure (Guardian)",
                    "type_time": int(self.client.ORDER_TIME_GTC),
                    "type_filling": int(self.client.ORDER_FILLING_IOC),
                }
                res = self.client.eval(f"mt5.order_send({repr(request)})")
                if res.retcode == self.client.TRADE_RETCODE_DONE:
                    print(f"✅ Closed {symbol} #{ticket}")
                else:
                    print(f"❌ Failed to close {symbol} #{ticket}: {res.comment}")
        except Exception as e:
            print(f"⚠️ Error during emergency closure: {e}")

    def close_all_positions_atomic(self):
        """Protocolo V3.8: Purga de Pendientes + Liquidación de Posiciones."""
        if not self.client: return
        try:
            # 1. PURGA DE ÓRDENES PENDIENTES
            pending_orders = self.client.orders_get()
            if pending_orders:
                logger.warning(f"🧹 [ORPHAN PURGE] Cancelling {len(pending_orders)} pending orders...")
                for o in pending_orders:
                    cancel_req = {
                        "action": int(self.client.TRADE_ACTION_REMOVE),
                        "order": int(o.ticket),
                        "comment": "Orphan Purge (V3.8)"
                    }
                    self.client.eval(f"mt5.order_send({repr(cancel_req)})")
                logger.info("✅ All pending orders cancelled.")

            # 2. LIQUIDACIÓN DE POSICIONES
            positions = self.client.positions_get()
            if not positions:
                logger.info("✅ No active positions to close.")
                return
            
            logger.warning(f"🌊 [LIQUIDATION] Closing {len(positions)} open positions...")
            for p in positions:
                side = 1 if p.type == 0 else 0 
                request = {
                    "action": int(self.client.TRADE_ACTION_DEAL),
                    "symbol": str(p.symbol), "volume": float(p.volume), "type": int(side), "position": int(p.ticket),
                    "price": float(self.client.symbol_info_tick(p.symbol).bid if side == 1 else self.client.symbol_info_tick(p.symbol).ask),
                    "deviation": 20, "magic": 99999, "comment": "Kaizen Final Liquidation",
                    "type_time": int(self.client.ORDER_TIME_GTC), "type_filling": int(self.client.ORDER_FILLING_IOC),
                }
                res = self.client.eval(f"mt5.order_send({repr(request)})")
                if res.retcode != self.client.TRADE_RETCODE_DONE:
                    logger.error(f"❌ Failed to close {p.symbol} #{p.ticket}: {res.comment}")
            
            logger.info("✅ Institutional Liquidation Complete (Account is 100% Cash).")
        except Exception as e:
            logger.error(f"⚠️ Error during Atomic Closure: {e}")


    def ensure_connected(self):
        """Called within the main loop to reconnect if dropped."""
        global MT5_CONNECTED, mt5_client
        if not self.client:
            return self.connect(max_retries=1)
            
        try:
            info = self.client.terminal_info()
            if info is None:
                # [FIX v4.6.0] Bridge corrupto: shutdown completo antes de reinit
                # para limpiar handles y memoria cache del terminal.
                print("⚠️ Handle corrupto detectado. Ejecutando shutdown limpio...")
                try: self.client.shutdown()
                except: pass
                self.client = None
                self.connected = False
                MT5_CONNECTED = False
                return self.connect(max_retries=3)
            return True
        except:
            print("⚠️ Connection lost! Reconnecting...")
            try: self.client.shutdown()
            except: pass
            self.connected = False
            MT5_CONNECTED = False
            return self.connect(max_retries=3)

                    
def check_basket_profit_lock(mt5_client, mt5_manager, bot):
    """
    [v10.2] BASKET LOCK DISABLED: Omega Core requiere que cada trade toque su TP/SL natural.
    El mapa de afinidad depende de la resolución binaria pura del nivel.
    """
    return

# --- [v10.0.0] MEMORIA DE PICOS Y ESTADÍSTICAS ---


def get_mt5_data(symbol, timeframe=None, bars=1000):
    if timeframe is None:
        timeframe = mt5_client.TIMEFRAME_M1
        
    rates = mt5_client.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None or len(rates) == 0:
        logger.warning(f"No MT5 data for {symbol} on {timeframe}")
        return None
        
    # Convert to DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df

mt5_manager = MT5ConnectionManager()

class MarketGuardian:
    """
    IRON SHIELD v2: Market Close Protection.
    Ensures speculative positions (Forex/Stocks) are closed before weekend gaps.
    Cryptos are excluded as they trade 24/7.
    """
    def __init__(self, mt5_client):
        self.mt5 = mt5_client
        self.crypto_keywords = ["BTC", "ETH", "SOL", "XRP", "LTC", "ADA", "DOT", "LINK", "DOGE"]
        self.close_window_minutes = 60  # Start monitoring 60 min before 4:00 PM EST
        self.hard_limit_minutes = 15   # Forced closure 15 min before 4:30 PM EST
        
    def is_crypto(self, symbol):
        return any(k in symbol.upper() for k in self.crypto_keywords)

    def get_est_time(self):
        """Converts current UTC time to EST (Eastern Standard Time)."""
        now_utc = datetime.now(timezone.utc)
        # EST is typically UTC-5
        return now_utc - timedelta(hours=5)

    def check_and_protect(self):
        """
        Main logic for Iron Shield v2.
        Sincronizado con el Reloj Maestro del Bróker (Server Time).
        """
        if not self.mt5: return
        
        # 1. LATIDO DE REFERENCIA: Sincronizar con el tiempo real del bróker
        tick = self.mt5.symbol_info_tick("EURUSD")
        if not tick: return
        
        server_now = datetime.fromtimestamp(tick.time)
        is_friday = server_now.weekday() == 4
        
        if not is_friday: return
        
        # 2. VENTANA DE LIQUIDACIÓN (Hora Servidor)
        # La mayoría de brókers cierran el viernes a las 23:59:59 (GMT+2/3)
        # 23:30 -> Smart Close (Asegurar ganancias)
        # 23:45 -> Hard Purge (Cierre total forzado)
        
        positions = self.mt5.positions_get()
        if not positions: return
        
        # IRON SHIELD DISABLED: Omega Core requiere pureza estadística.
        return

    def _close_position(self, p):
        """Helper to execute the close order."""
        symbol = p.symbol
        ticket = p.ticket
        type_close = 1 if p.type == 0 else 0 # Close Buy with Sell, Sell with Buy
        
        request = {
            "action": int(self.mt5.TRADE_ACTION_DEAL),
            "symbol": str(symbol),
            "volume": float(p.volume),
            "type": int(type_close),
            "position": int(ticket),
            "price": float(self.mt5.symbol_info_tick(symbol).bid if type_close == 1 else self.mt5.symbol_info_tick(symbol).ask),
            "deviation": int(20),
            "magic": int(10009),
            "comment": str("Iron Shield v2 Exit"),
            "type_time": int(self.mt5.ORDER_TIME_GTC),
            "type_filling": int(self.mt5.ORDER_FILLING_IOC),
        }
        
        res = self.mt5.eval(f"mt5.order_send({repr(request)})")
        if res.retcode != self.mt5.TRADE_RETCODE_DONE:
            logger.error(f"❌ IRON SHIELD v2 Failure: {res.comment} ({res.retcode})")
        else:
            logger.info(f"✅ IRON SHIELD v2 Success: Closed {symbol} #{ticket}")

market_guardian = None # To be initialized after MT5 connection

RISK_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "risk_cache.json")
risk_pips_cache = {}

def load_risk_cache():
    global risk_pips_cache
    if os.path.exists(RISK_CACHE_FILE):
        try:
            with open(RISK_CACHE_FILE, 'r') as f:
                data = json.load(f)
                # Convert keys to int (tickets are numbers)
                risk_pips_cache = {int(k): v for k, v in data.items()}
                logger.info(f"💾 Risk Cache Loaded: {len(risk_pips_cache)} entries.")
        except Exception as e:
            logger.error(f"❌ Error loading Risk Cache: {e}")

def save_risk_cache():
    try:
        with open(RISK_CACHE_FILE, 'w') as f:
            json.dump(risk_pips_cache, f)
    except Exception as e:
        logger.error(f"❌ Error saving Risk Cache: {e}")

# Load immediately
load_risk_cache()

def init_mt5():
    return mt5_manager.connect()

def get_initial_risk_pips(ticket, symbol, entry_p, point, pre_fetched_deals=None):
    """
    IRON SHIELD (Phase 5 Hardening):
    Scans history to find the REAL original stop-loss.
    Uses cache or pre-fetched deals to avoid redundant MT5 history queries.
    """
    global risk_pips_cache
    if ticket in risk_pips_cache:
        return risk_pips_cache[ticket]

    deals = pre_fetched_deals
    if deals is None:
        # Check history 1 year back to be safe (slow fallback)
        from_date = datetime.now() - timedelta(days=365)
        deals = mt5_client.history_deals_get(from_date, datetime.now(), position=ticket)
    
    if deals:
        for d in deals:
            # Filter by ticket if we have a mass list
            d_ticket = getattr(d, 'position', -1)
            if pre_fetched_deals and d_ticket != ticket: continue
            
            # Entry deal (TYPE_BUY or TYPE_SELL and ENTRY_IN)
            d_entry = getattr(d, 'entry', -1)
            d_sl    = getattr(d, 'sl', 0)
            if d_entry == 0:  # 0 is ENTRY_IN in MT5
                if d_sl > 0:
                    risk_pips = abs(entry_p - d_sl) / (point + 1e-12)
                    risk_pips_cache[ticket] = risk_pips
                    save_risk_cache() # Persist new entry
                    return risk_pips
    
    return None


# Phase 30: Portfolio Mixto 2026 — Selección NY/Londres
DEFAULT_ASSET_MAP = {
    # MAJORS
    "EURUSD": "EURUSD", "GBPUSD": "GBPUSD", "USDJPY": "USDJPY", 
    "AUDUSD": "AUDUSD", "USDCAD": "USDCAD", "NZDUSD": "NZDUSD",
    # CROSSES
    "GBPJPY": "GBPJPY", "EURJPY": "EURJPY", "EURGBP": "EURGBP",
    "AUDJPY": "AUDJPY", "CHFJPY": "CHFJPY", "CADJPY": "CADJPY",
    "EURAUD": "EURAUD", "GBPAUD": "GBPAUD", "EURNZD": "EURNZD",
    "NZDJPY": "NZDJPY",
    # METALS & COMMODITIES
    "XAUUSD": "XAUUSD", "XAGUSD": "XAGUSD", "WTI": "WTI",
    # INDICES
    "NAS100": "NAS100", "SPX500": "SPX500", "DAX40": "DAX40", "US30": "US30",
    # CRYPTO
    "BTCUSD": "BTCUSD", "ETHUSD": "ETHUSD", "SOLUSD": "SOLUSD"
}

# Load Dynamic Portfolio (Phase 2 Automation)
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
portfolio_path = os.path.join(base_dir, "config", "portfolio.json")

if os.path.exists(portfolio_path):
    try:
        with open(portfolio_path, 'r') as f:
            dynamic_portfolio = json.load(f)
            ASSET_MAP = dynamic_portfolio.get("assets", DEFAULT_ASSET_MAP)
            logger.info(f"🔄 DYNAMIC PORTFOLIO LOADED: {list(ASSET_MAP.keys())}")
    except:
        ASSET_MAP = DEFAULT_ASSET_MAP
else:
    ASSET_MAP = DEFAULT_ASSET_MAP

MT5_SYMBOL_MAP = ASSET_MAP
logger.info(f"🚀 FINAL PORTFOLIO SYNC: {list(MT5_SYMBOL_MAP.keys())}")
MAX_SPREAD_PIPS = 4.0 # Slightly higher for crypto/crosses

PENDING_ORDER_BUFFER_PIPS = 2.0
LIMIT_ORDER_RETRACT_PIPS = 3.0

# Setup logging (Console + File)
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")

# Init ML
stop_hunt_model = StopHuntModel() if ML_ENABLED else None

# --- POLIMATA INTEL PERSISTENCE ---
POLIMATA_INTEL_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "polimata_intel.json")
polimata_intel = {"retrain_count": 0, "last_retrain_date": None}
# --- BASKET THEORY TELEMETRY (Phase 97) ---
BASKET_LOG = os.path.join(log_dir, "basket_theory.jsonl")
basket_lifetime_peak = 0.0
last_basket_fingerprint = set()
if os.path.exists(POLIMATA_INTEL_FILE):
    try:
        with open(POLIMATA_INTEL_FILE, 'r') as f:
            polimata_intel = json.load(f)
    except: pass

last_retrain_date = polimata_intel.get("last_retrain_date")
AI_RISK_FACTOR = 1.0 # Phase 14
last_trade_audit = 0 # Phase 15: Intelligent Management
last_risk_audit = 0 # Phase 16: System Synergy

# Init RL Managers
rl_manager = RLTrailingManager() if RL_AGENT_ENABLED else None
sniper_manager = MFESniperManager() if SNIPER_ENABLED else None

# AI GATES
GATEKEEPER_MODE = "ACTIVE" # "ACTIVE" (Blocks trades) or "SHADOW" (Logs only) or "OFF"
GATEKEEPER_MODEL_PATH = "models/gatekeeper_qnet_v2.pth"
GATEKEEPER_SCALER_PATH = "models/gatekeeper_scaler_v2.json"

# ─────────────────────────────────────────────────────────
# 🔴 CIRCUIT BREAKER — Protección Anti-Tilt por Par
#   Bloquea un par si ocurre CUALQUIERA de las dos condiciones:
#     1. ≥ 2 pérdidas consecutivas en el día UTC actual
#     2. Pérdida acumulada ≥ $80 en el día UTC actual
# ─────────────────────────────────────────────────────────
CB_MAX_CONSECUTIVE_LOSSES = 2     # Disparador 1: losses seguidos
CB_MAX_DAILY_LOSS_USD     = 80.0  # Disparador 2: pérdida diaria en $

def get_daily_pair_stats(symbol: str, max_loss_usd: float = 80.0) -> dict:
    """
    Consulta el historial de deals de MT5 para el día UTC actual
    y retorna las métricas del circuit breaker para un par específico.

    Args:
        symbol: El par a consultar.
        max_loss_usd: El límite dinámico de pérdida por par para hoy.
    """
    try:
        today_utc = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        deals = mt5_client.history_deals_get(today_utc, datetime.now(timezone.utc))
        if not deals:
            return {'consecutive_losses': 0, 'daily_loss_usd': 0.0, 'is_blocked': False, 'reason': ''}

        # Filtrar solo los deals del símbolo que cierran posición (profit != 0)
        sym_deals = sorted(
            [d for d in deals
             if getattr(d, 'symbol', '') == symbol
             and getattr(d, 'profit', 0) != 0],
            key=lambda d: d.time
        )

        daily_loss   = sum(getattr(d, 'profit', 0) for d in sym_deals if getattr(d, 'profit', 0) < 0)
        daily_loss   = abs(daily_loss)

        # Contar pérdidas consecutivas desde el final (más recientes primero)
        consecutive = 0
        for d in reversed(sym_deals):
            if getattr(d, 'profit', 0) < 0:
                consecutive += 1
            else:
                break  # Win interrumpe la racha

        # Evaluar umbrales
        blocked = False
        reason  = ''
        if consecutive >= CB_MAX_CONSECUTIVE_LOSSES:
            blocked = True
            reason  = f"{consecutive} pérdidas consecutivas (límite {CB_MAX_CONSECUTIVE_LOSSES})"
        elif daily_loss >= max_loss_usd:
            blocked = True
            reason  = f"Pérdida diaria ${daily_loss:.2f} ≥ ${max_loss_usd:.2f} (límite dinámico)"

        return {
            'consecutive_losses': consecutive,
            'daily_loss_usd':     daily_loss,
            'is_blocked':         blocked,
            'reason':             reason,
        }
    except Exception as e:
        logger.warning(f"⚠️ CB: Error calculando stats de {symbol}: {e}")
        return {'consecutive_losses': 0, 'daily_loss_usd': 0.0, 'is_blocked': False, 'reason': ''}

def run_retrain_background():
    """Worker function for background training to avoid blocking the main loop"""
    try:
        import subprocess
        logger.info("🧵 [LHN-THREAD] Auto-Retrain started in BACKGROUND MISSION (Concurrent with Trading).")
        
        # Execute training script as subprocess to ensure clean memory
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "train_all_specialized_agents.py")
        env_copy = os.environ.copy()
        env_copy["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        subprocess.run([sys.executable, script_path], check=True, env=env_copy)
        
        # --- UPDATE INTEL ---
        polimata_intel["retrain_count"] = polimata_intel.get("retrain_count", 0) + 1
        polimata_intel["last_retrain_date"] = datetime.now().strftime("%Y-%m-%d")
        with open(POLIMATA_INTEL_FILE, 'w') as f:
            json.dump(polimata_intel, f, indent=4)
            
        logger.info(f"🧠 [LHN-THREAD] Polimata Training #{polimata_intel['retrain_count']} completed and persisted.")
        logger.info("🧠 [LHN-THREAD] Specialized models updated on disk. Synergizing with live engine...")
        
    except Exception as e:
        logger.error(f"❌ [LHN-THREAD] Auto-Retrain Background Task Failed: {e}")

# --- [UNIVERSAL GUARDIAN v4.1: PROTOCOLO KAIZEN] ---
class UniversalGuardian:
    def __init__(self, initial_capital, logger=None):
        self.initial_capital = initial_capital
        self.peak_equity = initial_capital
        self.logger = logger
        self.daily_limit_pct = 3.0 # Max Daily Loss FTMO standard
        self.last_atr_baseline = {} # {pair: baseline_atr}

    def update(self, current_equity):
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

    def get_scalar_multiplier(self, current_equity):
        """Calcula el frenado escalar basado en la proximidad al límite diario."""
        if self.initial_capital <= 0: return 1.0
        drawdown_pct = abs(min(0, (current_equity - self.initial_capital) / self.initial_capital * 100))
        
        if drawdown_pct >= 2.5: return 0.15 # Frenado extremo
        if drawdown_pct >= 2.0: return 0.40 # Frenado fuerte
        if drawdown_pct >= 1.0: return 0.80 # Desaceleración inicial
        return 1.0

    
    def get_profit_lock_floor(self, current_equity):
        """
        Calcula el piso de protección basado en MICRO-CANASTAS (0.5% - 1.0%).
        Utiliza self.peak_equity para asegurar que el piso sea un TRINQUETE (Ratchet).
        """
        if self.initial_capital <= 0: return None
        peak_growth_pct = (self.peak_equity - self.initial_capital) / self.initial_capital * 100
        lock_pct = 0.0
        if peak_growth_pct >= 2.0: lock_pct = 1.50   
        elif peak_growth_pct >= 1.5: lock_pct = 1.25 
        elif peak_growth_pct >= 1.0: lock_pct = 0.75 
        elif peak_growth_pct >= 0.75: lock_pct = 0.50 
        elif peak_growth_pct >= 0.50: lock_pct = 0.25 
        
        if lock_pct > 0:
            return self.initial_capital * (1 + (lock_pct / 100))
        return None


    def calculate_progressive_lot(self, current_balance, symbol_info, sl_dist, risk_pct=0.005):
        """
        Proposal V2: Progressive Micro-Sizing Protocol
        Handles accounts < $500 with a stepped growth approach.
        """
        # 1. Base floor for all accounts
        lot_min = symbol_info.volume_min if symbol_info.volume_min > 0 else 0.01
        
        # 2. Case: Micro Account (< $500)
        if current_balance < 500:
            if current_balance < 100:
                # Survival Zone: Fixed minimum
                return lot_min
            else:
                # Growth Zone: 0.01 per $100 of balance
                # $150 -> 0.01, $250 -> 0.02, $350 -> 0.03
                steps = int(current_balance / 100)
                progressive_lot = steps * 0.01
                return max(lot_min, round(progressive_lot, 2))
        
        # 3. Case: Standard Account (>= $500)
        # Use mathematical risk-based sizing
        tick_size = symbol_info.trade_tick_size
        tick_value = symbol_info.trade_tick_value
        
        # Override for Skypie-Enel & Hunter X (1% risk) if balance is healthy or specified
        final_risk = risk_pct
        if "LHN_ENEL" in str(symbol_info.name) or "HUNTER_X" in str(symbol_info.name):
            final_risk = 0.01 
            
        if tick_size > 0 and tick_value > 0 and sl_dist > 0:
            risk_usd = current_balance * final_risk
            loss_per_lot = (sl_dist / tick_size) * tick_value
            lots_calculated = risk_usd / loss_per_lot if loss_per_lot > 0 else lot_min
            return max(lot_min, round(lots_calculated, 2))
        
        return lot_min

    def get_v_switch(self, pair, current_atr):
        """Ajusta el lotaje si la volatilidad actual duplica el promedio."""
        if pair not in self.last_atr_baseline:
            self.last_atr_baseline[pair] = current_atr
            return 1.0
        
        baseline = self.last_atr_baseline[pair]
        if current_atr > (baseline * 1.5):
            return baseline / current_atr # Proporción inversa
        return 1.0

# Initialize Universal Guardian
guardian = None # Will be initialized inside main()

def check_auto_retrain():
    """Check if it's Sunday and trigger background retraining"""
    global last_retrain_date
    now = datetime.now()
    
    # Sunday = 6
    if now.weekday() == 6:
        today_str = now.strftime("%Y-%m-%d")
        if last_retrain_date != today_str:
            # We set the date BEFORE starting to avoid race conditions spawning multiple threads
            last_retrain_date = today_str
            thread = threading.Thread(target=run_retrain_background, daemon=True)
            thread.start()

def get_mt5_data(symbol, bars=200):
    """Fetch M15 data from MT5 Bridge."""
    if not MT5_CONNECTED: return pd.DataFrame()
    
    try:
        # TIMEFRAME_H1 = 16385
        tf = 16385 
        rates = mt5_client.copy_rates_from_pos(symbol, tf, 0, bars)
        
        if rates is None or len(rates) == 0:
            return pd.DataFrame()
            
        data = []
        for r in rates: data.append(list(r))
            
        df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume'])
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        return df
    except Exception as e:
        logger.error(f"MT5 Data Error ({symbol}): {e}")
        return pd.DataFrame()

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(period).mean()

def calculate_core_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    [NEME FIX] Inyecta los indicadores matemáticos necesarios para que 
    ForexInfantry y StrategyHub puedan "ver" el mercado.
    """
    if df.empty or len(df) < 50:
        return df

    # EMAs
    df['ema_5'] = df['close'].ewm(span=5, adjust=False).mean()
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_13'] = df['close'].ewm(span=13, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['ema_8'] = df['close'].ewm(span=8, adjust=False).mean()
    df['ema_16'] = df['close'].ewm(span=16, adjust=False).mean()
    df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()

    # ATR
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()

    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))

    # ADX
    plus_dm = df['high'].diff()
    minus_dm = df['low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    minus_dm = abs(minus_dm)
    tr_smooth = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / (tr_smooth + 1e-9))
    minus_di = 100 * (minus_dm.rolling(14).mean() / (tr_smooth + 1e-9))
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
    df['adx'] = dx.rolling(14).mean()

    # --- [CRYPTO LAB SUPPORT] ---
    # Bollinger Bands (Necesario para Squeeze Momentum)
    sma_20 = df['close'].rolling(window=20).mean()
    std_20 = df['close'].rolling(window=20).std()
    df['bb_upper'] = sma_20 + (std_20 * 2)
    df['bb_lower'] = sma_20 - (std_20 * 2)

    # Alias de Volumen (CryptoLab busca 'volume')
    if 'tick_volume' in df.columns:
        df['volume'] = df['tick_volume']
    
    # Rellenar NaNs iniciales por la ventana de cálculo
    df.bfill(inplace=True)

    return df

def analyze_hybrid_signal(df, symbol, indicators=None):
    if indicators is None: indicators = {}
    """
    Core Logic: HIVE V5 — Multi-Strategy Engine (Phase 15)
    Evaluates: ZENITH (Cons), HIVE V6 (Agg), and ORION (Pullback).
    """
    # --- INDICATOR CALCULATIONS ---
    # EMAs
    df['ema_5'] = df['close'].ewm(span=5, adjust=False).mean()
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_13'] = df['close'].ewm(span=13, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['ema_8'] = df['close'].ewm(span=8, adjust=False).mean()
    df['ema_16'] = df['close'].ewm(span=16, adjust=False).mean()
    df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()

    # ATR
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()

    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))

    # ADX
    plus_dm = df['high'].diff()
    minus_dm = df['low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    minus_dm = abs(minus_dm)
    tr_smooth = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / (tr_smooth + 1e-9))
    minus_di = 100 * (minus_dm.rolling(14).mean() / (tr_smooth + 1e-9))
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
    df['adx'] = dx.rolling(14).mean()

    # Bollinger Bands
    df['bb_mid'] = df['close'].rolling(20).mean()
    std = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_mid'] + (std * 2)
    df['bb_lower'] = df['bb_mid'] - (std * 2)
    
    # Rolling High/Low 24
    df['rolling_high_24'] = df['high'].rolling(24).max()
    df['rolling_low_24'] = df['low'].rolling(24).min()

    # --- MULTI-EMA ENGINE (Laboratory 2.0) ---
    def get_cross(s1, s2):
        c1 = df[s1].iloc[-2]; n1 = df[s1].iloc[-1]
        c2 = df[s2].iloc[-2]; n2 = df[s2].iloc[-1]
        if c1 <= c2 and n1 > n2: return 1
        if c1 >= c2 and n1 < n2: return -1
        return 0

    cross_9_15 = get_cross('ema_9', 'ema_15')
    cross_8_16 = get_cross('ema_8', 'ema_16')
    cross_12_26 = get_cross('ema_12', 'ema_26')

    row = df.iloc[-1]
    triggers = []
    
    # SYSTEM 1: LHN (Standard + Fractal Evolution)
    last_cross = cross_9_15
    sig = 0; strategy = "None"
    
    # --- VARIANTE A: ZENITH (Conservative) ---
    if last_cross != 0 and row['adx'] > 25:
        if last_cross == 1 and row['close'] > row['ema_200'] and row['rsi'] > 50:
            sig = 1; strategy = "ZENITH (Conservative)"
        elif last_cross == -1 and row['close'] < row['ema_200'] and row['rsi'] < 50:
            sig = -1; strategy = "ZENITH (Conservative)"
            
    # --- VARIANTE B: HIVE V6 (Aggressive) ---
    if sig == 0 and last_cross != 0 and row['adx'] > 18:
        if last_cross == 1 and row['close'] > row['ema_200'] and row['rsi'] > 45:
            sig = 1; strategy = "HIVE V6 (Aggressive NY)"
        elif last_cross == -1 and row['close'] < row['ema_200'] and row['rsi'] < 55:
            sig = -1; strategy = "HIVE V6 (Aggressive NY)"
            
    # --- VARIANTE C: ORION (Pullback Sniper) ---
    if sig == 0 and row['adx'] > 20:
        prev_rsi = df['rsi'].iloc[-2]
        if row['ema_9'] > row['ema_15'] and row['close'] > row['ema_200']:
            if prev_rsi < 45 and row['rsi'] >= 45:
                sig = 1; strategy = "ORION (Pullback Sniper)"
        elif row['ema_9'] < row['ema_15'] and row['close'] < row['ema_200']:
            if prev_rsi > 55 and row['rsi'] <= 55:
                sig = -1; strategy = "ORION (Pullback Sniper)"

    # --- FASE 16: MOTOR DE PROSPECCIÓN FRACTAL (Micro-Lots) ---
    if sig == 0:
        # FRACTAL ALPHA: Fast Momentum (EMA 5/13)
        df['ema_5']  = df['close'].ewm(span=5,  adjust=False).mean()
        df['ema_13'] = df['close'].ewm(span=13, adjust=False).mean()
        c5 = df['ema_5'].iloc[-2]; n5 = df['ema_5'].iloc[-1]
        c13 = df['ema_13'].iloc[-2]; n13 = df['ema_13'].iloc[-1]
        
        if c5 <= c13 and n5 > n13 and row['rsi'] > 50:
            sig = 1; strategy = "FRACTAL ALPHA (Fast EMA)"
        elif c5 >= c13 and n5 < n13 and row['rsi'] < 50:
            sig = -1; strategy = "FRACTAL ALPHA (Fast EMA)"
            
    if sig == 0:
        # FRACTAL BETA: Mean Reversion (Extreme RSI + Low ADX)
        if row['adx'] < 20:
            if row['rsi'] < 30:
                sig = 1; strategy = "FRACTAL BETA (Mean Reversion)"
            elif row['rsi'] > 70:
                sig = -1; strategy = "FRACTAL BETA (Mean Reversion)"

    # --- CRYPTO-SPECIALIZED: SKYPIE-ENEL (MCA Gold Clusters) ---
    enel_passed = False
    if sig != 0 and ENEL_ENABLED and any(c in symbol for c in ["BTC", "ETH", "SOL"]):
        # Fetch actual ML risk score if available in indicators or use a fallback
        # In a real run, this would be passed from a global model
        mock_ml_prob = indicators.get('ml_prob', 0.75) 
        if ENEL_ENGINE.evaluate(symbol, row, mock_ml_prob):
            strategy = f"⚡ SKYPIE-ENEL ({strategy})"
            enel_passed = True
        else:
            # If it's a crypto trade but fails Enel's Gold Cluster/Death Zone check, we abort
            # logger.info(f"🚫 [Skypie-Enel] Setup blocked for {symbol} (Death Zone found)")
            sig = 0; strategy = "None"

    # --- FOREX-SPECIALIZED: HUNTER X (MCA Elite Associations) ---
    if sig != 0 and HUNTER_X_ENABLED and not any(c in symbol for c in ["BTC", "ETH", "SOL"]):
        mock_ml_prob = indicators.get('ml_prob', 0.82) 
        if HUNTER_X_ENGINE.evaluate(symbol, row, mock_ml_prob):
            strategy = f"🎯 HUNTER X ({strategy})"
        else:
            # Hunter X is strictly elite. If it fails, we keep standard HIVE but without the Hunter X badge.
            pass

    if sig == 0:
        # FRACTAL GAMMA: Chaos Breakout (L3 H/L)
        l3 = df.iloc[-4:-1]
        if row['close'] > l3['high'].max():
            sig = 1; strategy = "FRACTAL GAMMA (L3 Breakout)"
        elif row['close'] < l3['low'].min():
            sig = -1; strategy = "FRACTAL GAMMA (L3 Breakout)"

    # --- FASE 17: EL DESAFÍO DE LA MEJOR (TEMP 2) ---
    if sig == 0:
        # FRACTAL DELTA: Liquidity Sweep (Stop Hunt Hunter)
        prev_h = df['rolling_high_24'].iloc[-2]
        prev_l = df['rolling_low_24'].iloc[-2]
        if df['low'].iloc[-1] < prev_l and row['close'] > prev_l and row['rsi'] < 40:
            sig = 1; strategy = "FRACTAL DELTA (Liquidity Sweep)"
        elif df['high'].iloc[-1] > prev_h and row['close'] < prev_h and row['rsi'] > 60:
            sig = -1; strategy = "FRACTAL DELTA (Liquidity Sweep)"

    if sig == 0:
        # FRACTAL EPSILON: Institutional Mean Reversion
        if row['rsi'] < 30 and row['close'] < row['bb_lower']:
            sig = 1; strategy = "FRACTAL EPSILON (Mean Reversion)"
        elif row['rsi'] > 70 and row['close'] > row['bb_upper']:
            sig = -1; strategy = "FRACTAL EPSILON (Mean Reversion)"

    if sig == 0:
        # FRACTAL ZETA: ADX Squeeze / Explosion
        prev_adx = df['adx'].iloc[-2]
        if prev_adx < 15 and row['adx'] >= 17:
            if row['ema_9'] > row['ema_15']:
                sig = 1; strategy = "FRACTAL ZETA (ADX Squeeze)"
            elif row['ema_9'] < row['ema_15']:
                sig = -1; strategy = "FRACTAL ZETA (ADX Squeeze)"

    if sig == 0:
        # FRACTAL ETA: Ghost Sniper (SMC / FVG)
        c0 = df.iloc[-1]; c1 = df.iloc[-2]; c2 = df.iloc[-3]
        fvg_bull = c0['low'] > c2['high']
        fvg_bear = c0['high'] < c2['low']
        if fvg_bull and row['close'] > row['ema_200'] and row['rsi'] < 55:
            sig = 1; strategy = "FRACTAL ETA (Ghost Sniper)"
        elif fvg_bear and row['close'] < row['ema_200'] and row['rsi'] > 45:
            sig = -1; strategy = "FRACTAL ETA (Ghost Sniper)"

    if sig != 0:
            dir_str = "BUY" if sig == 1 else "SELL"
            logger.info(f"📡 [RAW ALPHA] {symbol}: {strategy} (LHN) sugiere {dir_str}. Ingresando al Pool.")
            triggers.append((sig, strategy, row, "LHN"))

    # SYSTEM 2: LAB 2.1 (EMA 8/16)
    if cross_8_16 != 0:
            dir_str = "BUY" if cross_8_16 == 1 else "SELL"
            logger.info(f"📡 [RAW ALPHA] {symbol}: LAB_E8_E16 (E8E16) sugiere {dir_str}. Ingresando al Pool.")
            triggers.append((cross_8_16, "LAB_E8_E16", row, "E8E16"))

    # SYSTEM 3: LAB 2.1 (EMA 12/26)
    if cross_12_26 != 0:
            dir_str = "BUY" if cross_12_26 == 1 else "SELL"
            logger.info(f"📡 [RAW ALPHA] {symbol}: LAB_E12_E26 (E12E26) sugiere {dir_str}. Ingresando al Pool.")
            triggers.append((cross_12_26, "LAB_E12_E26", row, "E12E26"))

    return triggers

def get_filling_mode(symbol_info):
    """
    Returns the correct order filling mode supported by the broker for this symbol.
    Tries FOK first, then IOC, then RETURN (Market) as fallback.
    """
    filling_type = symbol_info.filling_mode
    if filling_type & 1:  # ORDER_FILLING_FOK
        return mt5_client.ORDER_FILLING_FOK
    elif filling_type & 2:  # ORDER_FILLING_IOC
        return mt5_client.ORDER_FILLING_IOC
    else:
        return mt5_client.ORDER_FILLING_RETURN


def normalize_symbol_name(raw_name):
    """
    Universal Symbol Normalizer (Phase 93 Hardening):
    Converts broker-specific names (eumnzd, EURUSD.m, etc.) 
    to standard 6-character root pairs (EURNZD, EURUSD).
    """
    if not raw_name: return ""
    name = raw_name.upper()
    
    # 1. Handle common Axi/Broker prefixes
    if name.startswith("EUM"): # e.g. eumnzd -> EUMNZD -> EURNZD
        # Specific fix for Axi 'eum' micro prefix
        name = "EUR" + name[3:]
        
    # 2. Strip common suffixes (.m, .mini, .cfd, etc.)
    for suffix in [".M", ".MINI", ".CFD", ".SB", "!"]:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
            
    # 3. Handle Special Case for Gold/Silver
    if "XAUUSD" in name: return "XAUUSD"
    if "XAGUSD" in name: return "XAGUSD"
    
    # 4. Extract first 6 characters for Forex pairs
    # (Safe for most standard and suffixed pairs)
    if len(name) >= 6:
        return name[:6]
        
    return name


def execute_mt5_trade(pair, final_direction, price, sl, tp, volume, comment="Nanobot HIVE v6.8", use_virtual_sl=True):
    """
    [v9.0.0] NATIVE MT5 EXECUTION ENGINE + STEALTH AEGIS
    - final_direction: 1 or "BUY", -1 or "SELL"
    """
    if not MT5_CONNECTED: return
    
    symbol_mt5 = MT5_SYMBOL_MAP.get(pair, pair)
    if not mt5_client.symbol_select(symbol_mt5, True):
        logger.error(f"❌ Impossible to select/awake symbol: {symbol_mt5}")
        return None

    # Normalización de dirección (acepta String o Int)
    is_buy = (final_direction == 1 or str(final_direction).upper() == "BUY")

    if not check_correlation_exposure(pair, final_direction):
        return None
    
    info = mt5_client.symbol_info(symbol_mt5)
    tick = mt5_client.symbol_info_tick(symbol_mt5)
    if not info or not tick:
        logger.error(f"❌ Symbol Info/Tick Failed: {symbol_mt5}")
        return
        
    # Guardar el SL real para el Escudo Sigiloso
    real_sl = sl
    if use_virtual_sl:
        sl = 0.0 # Ocultar el riesgo al bróker
        if real_sl > 0:
            comment += f"_VSL{real_sl:.5f}"

    pip_val = info.point 
    pips_in_point = 10 if ("USD" in pair and "JPY" not in pair and "XAU" not in pair and "BTC" not in pair) else 1
    buffer_val = PENDING_ORDER_BUFFER_PIPS * info.point * pips_in_point
    filling_mode = get_filling_mode(info)
    
    sl_dist = abs(price - sl) if sl > 0 else 0
    tp_dist = abs(price - tp) if tp > 0 else 0
    
    # [v6.8.3] NATIVE NUMERIC LOGIC
    if is_buy: # BUY
        target_price = max(price, tick.ask + buffer_val) if price > tick.ask else price
        sl = target_price - sl_dist if sl_dist > 0 else 0
        tp = target_price + tp_dist if tp_dist > 0 else 0
    else: # SELL
        target_price = min(price, tick.bid - buffer_val) if price < tick.bid else price
        sl = target_price + sl_dist if sl_dist > 0 else 0
        tp = target_price - tp_dist if tp_dist > 0 else 0
        
    price = target_price
    stops_level = info.trade_stops_level * info.point
    min_dist = stops_level * 1.5 
    
    if is_buy:
        if abs(price - tick.ask) < min_dist: price = tick.ask + min_dist
    else:
        if abs(price - tick.bid) < min_dist: price = tick.bid - min_dist

    # Normalization
    step_vol = info.volume_step
    if step_vol > 0: volume = round(volume / step_vol) * step_vol
    volume = round(max(info.volume_min, min(info.volume_max, volume)), 2)
    price, sl, tp = round(price, info.digits), round(sl, info.digits), round(tp, info.digits)
    
    # [v6.8.3] NATIVE MT5 ACTION MAPPING
    action = mt5_client.TRADE_ACTION_PENDING
    if is_buy:
        if price <= tick.ask:
            type_mt5 = mt5_client.ORDER_TYPE_BUY_LIMIT
            if abs(price - tick.ask) < info.point: 
                action = mt5_client.TRADE_ACTION_DEAL
                type_mt5 = mt5_client.ORDER_TYPE_BUY
        else:
            type_mt5 = mt5_client.ORDER_TYPE_BUY_STOP
    else:
        if price >= tick.bid:
            type_mt5 = mt5_client.ORDER_TYPE_SELL_LIMIT
            if abs(price - tick.bid) < info.point:
                action = mt5_client.TRADE_ACTION_DEAL
                type_mt5 = mt5_client.ORDER_TYPE_SELL
        else:
            type_mt5 = mt5_client.ORDER_TYPE_SELL_STOP
        
    request = {
        "action": int(action),
        "symbol": str(symbol_mt5),
        "volume": float(volume),
        "price": float(price),
        "sl": float(sl),
        "tp": float(tp),
        "type": int(type_mt5),
        "type_time": int(mt5_client.ORDER_TIME_DAY), 
        "type_filling": int(filling_mode),
        "comment": "".join(c for c in str(comment) if ord(c) < 128)[:31],
    }
    
    # [DOUBLE-SHIELD v4.9.1] Limpieza forzada de tipos para evitar proxies de RPyC
    clean_request = {}
    for k, v in request.items():
        if isinstance(v, (int, float, str)):
            clean_request[k] = v
        else:
            try:
                # Si es un proxy de RPyC, int() o float() lo resolverán
                if k in ["volume", "price", "sl", "tp"]:
                    clean_request[k] = float(v)
                else:
                    clean_request[k] = int(v)
            except:
                clean_request[k] = str(v)
    
    request = clean_request
    
    max_trade_retries = 2
    for attempt in range(max_trade_retries):
        try:
            # [FIX v4.8.0] BYPASS: No usamos mt5_client.order_send() porque la librería
            # tiene un bug en la firma del método que rompe la serialización RPyC.
            # Al usar eval() con repr() local, garantizamos una ejecución atómica.
            result = mt5_client.eval(f"mt5.order_send({repr(request)})")
            
            # Blindaje de Seguridad v4.5.1: Validar respuesta del terminal con re-intento
            if result is None:
                last_err = mt5_client.last_error()
                if attempt == 0:
                    err_msg = f"❌ TERMINAL TIMEOUT (Intento 1) | MT5_ERR: {last_err} | RE-SINCRONIZANDO {pair}..."
                    logger.error(err_msg)
                    # Re-inicialización en caliente
                    mt5_manager.connect(max_retries=1)
                    time.sleep(1.0)  # Pausa de estabilización mecánica
                    continue  # Reintentar el envío de la orden
                else:
                    err_msg = f"❌ TERMINAL TIMEOUT FATAL: Puente Silicon no responde tras re-intento para {pair}."
                    logger.error(err_msg)
                    return None

            if result.retcode != mt5_client.TRADE_RETCODE_DONE:
                err_msg = f"❌ ORDER FAILED: {symbol_mt5} {result.comment} ({result.retcode})"
                logger.error(err_msg)
                
                # Silenciador v4.5.0: Evitar 429 de Telegram
                global LAST_TELEGRAM_ERROR_TIME
                if bot.enabled and (time.time() - LAST_TELEGRAM_ERROR_TIME > TELEGRAM_ERROR_COOLDOWN):
                    bot.send_message(err_msg)
                    LAST_TELEGRAM_ERROR_TIME = time.time()
            else:
                order_tick = getattr(result, 'order', 0)
                success_msg = f"✅ ORDER PLACED: {pair} #{order_tick} | Price: {result.price:.5f}"
                logger.info(success_msg)
                if bot.enabled: bot.send_message(success_msg)
            return result
        except Exception as e:
            logger.error(f"⚠️ Execution Exception on {pair}: {e}")
            return None

def cleanup_pending_orders():
    """Report pending orders generated by Hive V5."""
    if not MT5_CONNECTED: return
    try:
        orders = mt5_client.orders_get()
        if not orders: 
            print("✅ NO Active Pending Orders.")
            return
        
        print(f"\n📋 PENDING ORDERS REPORT ({len(orders)}):")
        print("-" * 60)
        for o in orders:
            # Check comment signature: "Nanobot HIVE V5"
            is_hive = "Nanobot" in o.comment
            
            # Phase 8 Verification: Check if SL is synchronized
            sl_sync_status = "⚠️ SL MISSING"
            if o.sl > 0:
                # Prove Iron Shield compatibility: SL diff in pips
                info = mt5_client.symbol_info(o.symbol)
                if info:
                    sl_pips = abs(o.price_open - o.sl) / info.point
                    sl_sync_status = f"✅ SL SYNC ({sl_pips:.1f} pips)"
            
            print(f"#{o.ticket} | {o.symbol} | {o.type} | Open: {o.price_open} | {sl_sync_status} | Hive: {is_hive}")
            print("-" * 60)
            
            # AUTO-DELETE DISABLED BY USER REQUEST
            # if is_hive: ...
                
    except Exception as e:
        print(f"Cleanup Error: {e}")

# --- PHASE 14: INSTITUTIONAL RISK MANAGER 🏦 ---
AI_RISK_FACTOR = 1.0 # Default Global Multiplier from Gemini

def calculate_institutional_risk(current_balance, daily_start_balance, current_equity, atr, avg_atr, base_risk=0.004):
    """
    Dynamic Risk Scaling based on Drawdown and Volatility.
    """
    risk_multiplier = 1.0
    
    # 1. Drawdown Shield
    daily_dd = daily_start_balance - current_equity
    daily_dd_pct = (daily_dd / daily_start_balance) * 100
    
    if daily_dd_pct > 2.0:
        risk_multiplier *= 0.5 # Halve risk if down > 2% today
        print(f"🛡️ DRAWDOWN SHIELD ACTIVE: Risk halved (DD={daily_dd_pct:.2f}%)")

    # 2. Volatility Scaling (ATR)
    # If current ATR is 2x average, market is exploding (News/Crash)
    if avg_atr > 0 and atr > (avg_atr * 2.0):
        risk_multiplier *= 0.5
        print(f"📉 VOLATILITY GUARD: ATR Spike detected ({atr:.4f} vs {avg_atr:.4f})")

    # 3. AI Overlay
    if AI_RISK_FACTOR < 1.0:
        risk_multiplier *= AI_RISK_FACTOR
        print(f"🧠 AI RISK OFFICER: Risk scaled by {AI_RISK_FACTOR}")

    final_risk = base_risk * risk_multiplier
    return final_risk


def check_correlation_exposure(new_pair, new_type):
    if not MT5_CONNECTED: return True 
    symbol_mt5 = MT5_SYMBOL_MAP.get(new_pair, new_pair)
    positions = mt5_client.positions_get(symbol=symbol_mt5)
    orders = mt5_client.orders_get(symbol=symbol_mt5)
    active_count = (len(positions) if positions else 0) + (len(orders) if orders else 0)
    if active_count >= 8:
        logger.debug(f"🛑 SYMBOL CAP: {new_pair} ya tiene {active_count} niveles (Max 8).")
        return False
    return True
 
    
    positions = mt5_client.positions_get()
    orders = mt5_client.orders_get()
    
    # 1. ALERTA DE CONCENTRACIÓN: No operar si ya hay algo abierto en este par
    existing_pos = [p for p in positions if p.symbol == ASSET_MAP.get(new_pair)] if positions else []
    existing_orders = [o for o in orders if o.symbol == ASSET_MAP.get(new_pair)] if orders else []
    
    if len(existing_pos) > 0 or len(existing_orders) > 0:
        print(f"🚫 CONCENTRATION RISK: Already have active exposure in {new_pair}. Skipping.")
        return False

    # 2. TOPE DE CARTERA: Máximo 10 trades simultáneos en todo el sistema
    total_exposure = (len(positions) if positions else 0) + (len(orders) if orders else 0)
    if total_exposure >= 10:
        print(f"🛑 PORTFOLIO CAP: Max concurrent trades (10) reached. Skipping {new_pair}.")
        return False

    # 3. Check USD Direction and Asset Class Saturation
    is_usd_pair = "USD" in new_pair
    # Clasificación mejorada para Portfolio Mixto 2026
    if "BTC" in new_pair:
        asset_class = "CRYPTO"
    elif "XAU" in new_pair:
        asset_class = "METALS"
    else:
        asset_class = "FOREX"
    
    class_direction_count = 0
    usd_longs = 0
    usd_shorts = 0
    
    # Check current data for directional saturation
    active_items = []
    if positions: active_items.extend(positions)
    if orders: active_items.extend(orders)

    for p in active_items:
        symbol = p.symbol
        p_type = p.type # 0=Buy, 1=Sell
        
        # Asset Class Direction Check
        if "BTC" in symbol:
            p_asset_class = "CRYPTO"
        elif "XAU" in symbol:
            p_asset_class = "METALS"
        else:
            p_asset_class = "FOREX"
            
        if p_asset_class == asset_class:
            is_buy = "BUY" in new_type or "BS" in new_type
            p_is_buy = (p_type == 0) # Simple map for demo, MT5 uses specific enums for orders
            if is_buy == p_is_buy:
                class_direction_count += 1
                
        if "USD" in symbol:
            # Phase 4 Logic Hardening: Distinguish Base vs Quote USD
            is_usd_base = symbol.startswith("USD")
            if is_usd_base:
                if p_type == 0: usd_longs += 1 # Buying USDCAD = Buying USD
                else: usd_shorts += 1
            else:
                if p_type == 0: usd_shorts += 1 # Buying EURUSD = Selling USD
                else: usd_longs += 1
             
    # 4. Apply Advanced Filters
    if class_direction_count >= 3: # Relaxed from 2 to 3 for Full Activation
        print(f"🔗 ASSET CLASS SATURATION: Already 3 trades in same direction for {asset_class}. Blocking {new_pair}.")
        return False

    # Evaluate New Trade USD Correlation
    if is_usd_pair:
        new_is_buy = "BUY" in new_type or "BS" in new_type
        new_is_usd_base = new_pair.startswith("USD")
        
        # Determine if new trade is Buying or Selling USD
        if new_is_usd_base:
            is_selling_usd = not new_is_buy
        else:
            is_selling_usd = new_is_buy
            
        if is_selling_usd:
            if usd_shorts >= 3: # Aumentado de 2 a 3 para Portfolio Mixto where 5/5 assets have USD
                print(f"🔗 CORRELATION FILTER: Too many USD Shorts ({usd_shorts}). Blocking {new_pair}.")
                return False
        else:
            if usd_longs >= 3:
                print(f"🔗 CORRELATION FILTER: Too many USD Longs ({usd_longs}). Blocking {new_pair}.")
                return False
            
    return True


def manage_active_trades(bot_brain):
    """
    Apply Intelligent Management (Phase 15):
    - Auto Break Even (BE)
    - AI Guardian Audit (Gemini)
    """
    from types import SimpleNamespace
    global last_trade_audit
    if not MT5_CONNECTED: return
    
    positions_proxy = mt5_client.positions_get()
    if not positions_proxy: return
    
    # SERIALIZATION OPTIMIZATION (Kaido 2026): Local Mocks for Ultra-Fast RPyC
    positions = [SimpleNamespace(**p._asdict()) for p in positions_proxy]
    
    # BATCH OPTIMIZATION (Kaido 2026): Fetch only NECESSARY history
    min_pos_time = min([p.time for p in positions])
    from_date = datetime.fromtimestamp(min_pos_time) - timedelta(days=2)
    deals_proxy = mt5_client.history_deals_get(from_date, datetime.now())
    all_deals = [SimpleNamespace(**d._asdict()) for d in deals_proxy] if deals_proxy else []
    
    # CACHE RATES & INFO (Kaido 2026)
    symbol_rates_cache = {}
    symbol_info_cache = {}
    
    current_time = time.time()
    curr_hour = datetime.now().hour
    active_summary = []
    
    for p in positions:
        try:
            symbol = p.symbol
            
            # Get Symbol Context (ATR/Digits) - CACHED
            if symbol not in symbol_info_cache:
                info = mt5_client.symbol_info(symbol)
                symbol_info_cache[symbol] = info
            else:
                info = symbol_info_cache[symbol]
                
            if not info: continue
            
            # Get last ATR (Native MT5) with CACHE
            if symbol not in symbol_rates_cache:
                rates = mt5_client.copy_rates_from_pos(symbol, 16385, 0, 20) # H1
                symbol_rates_cache[symbol] = rates
            else:
                rates = symbol_rates_cache[symbol]

            if rates is not None and len(rates) > 14:
                df = pd.DataFrame(rates)
            else:
                df = pd.DataFrame()
            
            # --- [v10.2] ACTIVE POSITION MANAGEMENT DISABLED ---
            # Omega Core requiere que cada trade toque su TP/SL natural para evitar contaminar el Mapa de Calor.
            # No se permiten Breakevens, Cierres Parciales, Trailing Stops ni Virtual SLs.
            pass
            
            duration_hours = (datetime.now() - datetime.fromtimestamp(p.time)).total_seconds() / 3600
            
            active_summary.append({
                'ticket': int(p.ticket),
                'symbol': symbol,
                'type': int(p.type),
                'profit_pips': float(p.profit),
                'duration_hours': duration_hours
            })

        except Exception as e:
            logger.error(f"Error managing position {p.symbol if 'p' in locals() else 'unknown'}: {e}")

    # 🧠 AI Audit (Informational Only)
    if bot_brain and (current_time - last_trade_audit > 1800):
        last_trade_audit = current_time

def main():
    print("DEBUG: L1545 - ENTERING MAIN")
    global current_capital, AI_RISK_FACTOR, last_trade_audit, last_risk_audit, last_pulse_time, circuit_breaker_cooldown, GATEKEEPER_MODE
    global STRATEGY_HUB_ENABLED, STRATEGY_HUB, GLOBAL_RESUME_TIME, mega_grid_tracker, RISK_PER_TRADE
    circuit_breaker_cooldown = 0
    
    # 1. Report Orders on Start (Skipped if not connected)
    if MT5_CONNECTED: cleanup_pending_orders()
    
    # 2. Nanobot Intelligence Briefing (DISABLED)
    # try:
    #     from src.nanobot.supervisor import NanobotSupervisor
    #     bot_brain = NanobotSupervisor(model_name="gemini/gemini-2.0-flash")
    #     
    #     # Gather Context
    #     ctx = {
    #         'pairs_count': len(ASSET_MAP),
    #         'adx_threshold': 20, 
    #         'avg_volatility': "Analizing..." 
    #     }
    #     
    #     print("\n🧠 NANOBOT INTELLIGENCE (Gemini): DISABLED")
    #     print("-" * 60)
    #     # briefing = bot_brain.generate_daily_briefing(ctx)
    #     # print(f"💬 {briefing}")
    #     
    #     # --- PHASE 14: AI RISK ASSESSMENT ---
    #     global AI_RISK_FACTOR
    #     # risk_assessment = bot_brain.assess_global_risk(ctx)
    #     # AI_RISK_FACTOR = risk_assessment.get('risk_factor', 1.0)
    #     # print(f"🛡️ RISK OFFICER: {risk_assessment.get('reason', 'Proceeding with standard protocols.')}")
    #     print("-" * 60)
    #     
    # except Exception as e:
    #     print(f"⚠️ Intelligence Module Error: {e}")
    
    bot_brain = None # Placeholder

    # Initialize session start time for PnL tracking (Phase 29: Fresh Start)
    session_start_time = datetime.now()
    circuit_breaker_cooldown = 0
    
    # 3. Connect MT5 (Late Init to prevent hang)
    print("📡 INITIALIZING SILICON MT5 BRIDGE (AXI CHALLENGE)...")
    init_mt5()
    print("✅ SILICON MT5 BRIDGE INITIALIZED.")

    global vol_engine, risk_tribunal
    vol_engine = VolatilityEngine(mt5_client)
    risk_tribunal = MeritocraticRiskManager(mt5_client, global_cap=0.025)

    # Initialize Risk Oracle (Quantum RL-Ready)
    risk_oracle = None
    account_peak = 0.0
    if RISK_ORACLE_ENABLED:
        risk_oracle = AsymmetricRiskOracle(
            fraction=0.20, 
            rl_model_path="models/risk_oracle_rl_v1.zip"
        )
        
        # Initial Balance to start peak tracking
        if MT5_CONNECTED:
            acc_init = mt5_client.account_info()
            if acc_init:
                # [v6.2.0] PERSISTENCE RECOVERY (Anti-Amnesia)
                # Recuperar el estado térmico de la cuenta para no violar reglas de FTMO
                p_state = persistence_handler.validate_and_sync(account_peak, float(acc_init.equity))
                
                global current_capital, INITIAL_CAPITAL
                INITIAL_CAPITAL = p_state["daily_start_balance"] # ESTO YA NO SE PIERDE AL REINICIAR
                current_capital = float(acc_init.equity)
                account_peak = p_state["equity_peak"]
                
                logger.info(f"🧠 [MEMORY RECOVERED] FTMO Base: ${INITIAL_CAPITAL:.2f} | Peak: ${account_peak:.2f}")
                print(f"🏦 QUANTUM RISK RL: Active | Peak (Reset): ${account_peak:.2f}")

    # 4. Report Orders
    if MT5_CONNECTED: cleanup_pending_orders()   

    # Fallback de seguridad para el banner: Carga preventiva de riesgo
    try:
        _, RISK_PER_TRADE = load_tactical_config()
    except:
        RISK_PER_TRADE = 0.004

    print(f"""
    ╔══════════════════════════════════════════════════════╗
    ║   🦖 NANOBOT HIVE V5 (ALL-STARS EDITION) 🌟          ║
    ║   Assets: Top 11 Performers (AUD, GBP, JPY, Crypto)  ║
    ║   Mode:   H1 TREND SNIPER (Native FTMO Data)         ║
    ║   Risk:   {RISK_PER_TRADE*100:.1f}% (PF 1.32 Config)                     ║
    ║   Capital: ${current_capital:,.2f}                     ║
    ╚══════════════════════════════════════════════════════╝
    """)
    
    # Update Capital from MT5
    if MT5_CONNECTED:
        try:
            acc = mt5_client.account_info()
            if acc:
                current_capital = acc.balance
                print(f"💰 LIVE BALANCE SYNC: ${current_capital:,.2f} ({acc.currency})")
        except Exception as e:
            print(f"⚠️ Balance Sync Failed: {e}")
    
    # 0. Telegram Startup
    if bot.enabled:
        logger.info("📡 Sending Startup Message (Async)...")
        msg = "🦖 *HIVE V5 ALL-STARS LIVE* 🟢\nSuper-Swarm Active (26 Assets)\nScanning for SMC & Fractal Setups..."
        threading.Thread(target=bot.send_message, args=(msg,), daemon=True).start()
        
        # --- [v6.3.2] AFFINITY HARVESTER LAUNCH ---
        harvester_thread = threading.Thread(target=affinity_harvester_daemon, args=(mt5_client, logger), daemon=True)
        harvester_thread.start()
    
    global last_health_check, gatekeeper_agent
    
    # Initialize Gatekeeper
    if GATEKEEPER_MODE != "OFF":
        try:
            from src.nanobot.ml.gatekeeper import GatekeeperAgent
            # Update paths to be relative to project root
            gatekeeper_agent = GatekeeperAgent(GATEKEEPER_MODEL_PATH, GATEKEEPER_SCALER_PATH)
            if gatekeeper_agent.loaded:
                logger.info(f"🧠 Gatekeeper AI Loaded (Mode: {GATEKEEPER_MODE})")
            else:
                logger.warning("⚠️ Gatekeeper Failed to Load - Disabled")
                gatekeeper_agent = None
        except Exception as e:
            logger.error(f"❌ Gatekeeper Import Error: {e}")

    logger.info("🚀 Starting FTMO Guardian Bot (Manual/Signal Mode)...")
    
    if mt5_client is None or not MT5_CONNECTED:
        logger.critical("🛑 ABORTO DE MISIÓN: El puente MT5 no está operativo. El motor no puede arrancar a ciegas.")
        logger.critical("Verifique sus credenciales en config/credentials.json y el estado del servidor FTMO.")
        sys.exit(1) # Freno de mano absoluto
    # ----------------------------------------

    last_pulse_time = time.time()
    logger.info("⚡ Entering 24/7 Signal Scan Loop...")
    print(f"⏳ Scanning... (Ctrl+C to stop)")

    while True:
        try:
            # --- [V8.5.0] ROLLOVER & BUNKER PROTECTION ---
            if check_rollover_killswitch(mt5_client, persistence_handler):
                time.sleep(10)
                continue

            # Globals for components
            global market_guardian, orchestrator, meta_selector, guardian, GLOBAL_RESUME_TIME, STRATEGY_HUB_ENABLED, STRATEGY_HUB
            logger.debug("--- [STEP 0] Loop Start ---")

            # --- [v8.0.0] PROTOCOLO DE HIBERNACIÓN ---
            if persistence_handler.state.get("daily_goal_reached", False):
                if int(time.time()) % 1800 < 5:
                    logger.info("🐻 [HIBERNATION] Objetivo diario cumplido. Búnker cerrado hasta zona segura (02:00 UTC).")
                time.sleep(5)
                continue

            # --- [V3.7 GLOBAL GATEKEEPER] ---
            if time.time() < GLOBAL_RESUME_TIME:
                rem_s = int(GLOBAL_RESUME_TIME - time.time())
                if rem_s % 60 == 0:
                    logger.info(f"⏳ [COOLDOWN] System is cooling off. Resuming in {rem_s//60}m.")
                time.sleep(1)
                continue

            iteration_exposed_symbols = set() # Local tracking for current iteration
            
            # 0. Connection Watchdog
            if not mt5_manager.ensure_connected():
                logger.error("❌ Link Lost. Waiting for recovery...")
                time.sleep(5)
                continue
            logger.debug("--- [STEP 1] Connection Verified ---")

                        # --- [V3.6 GLOBAL GATEKEEPER] ---
            if time.time() < GLOBAL_RESUME_TIME:
                rem_s = int(GLOBAL_RESUME_TIME - time.time())
                if rem_s % 300 == 0: 
                    logger.info(f"⏳ [COOLDOWN] System is cooling off. Resuming in {rem_s//60}m.")
                time.sleep(5)
                continue

            # Update account info EVERY iteration
            acc = mt5_client.account_info()
            if not acc:
                logger.warning("⚠️ Failed to get account info. Skipping iteration.")
                time.sleep(1)
                continue
            
            # [v7.5.1] Get current positions for Risk & Basket Logic
            active_positions = mt5_client.positions_get() or []
            active_pos_count = len(active_positions)
                
            equity = acc.equity
            balance = acc.balance

            # --- [v6.2.4] INSTITUTIONAL CAPITAL SYNC ---
            # Sincronizar con la persistencia para obtener el balance de inicio de día real
            p_state = persistence_handler.validate_and_sync(balance, equity)
            daily_start = p_state.get("daily_start_balance", balance)
            
            # Blindaje contra 0
            if daily_start <= 0: daily_start = balance
            
            # Actualizar la constante global de riesgo
            INITIAL_CAPITAL = daily_start
            current_capital = balance # Live monitoring
            
            real_pnl = equity - INITIAL_CAPITAL
            
            # --- [v9.1.0] SOVEREIGNTY ORACLE ---
            sovereign_target = persistence_handler.calculate_sovereign_target(equity)
            is_stasis = sovereign_target == -1.0
            persistence_handler.state["sovereign_target_cache"] = sovereign_target
            persistence_handler.save()
            
            kill_pnl = get_rollover_kill_pnl(mt5_client)
            
            # Adjusted PnL ignores ROLLOVER_KILL losses for the Ratchet limit
            adjusted_pnl = real_pnl
            if kill_pnl < 0:
                adjusted_pnl = real_pnl - kill_pnl
            
            # --- [v6.7.0] DYNAMIC TRUST RATCHET: DAILY LOSS PROTECTION ---
            # Si el drawdown diario ajustado supera el -0.5%, castigamos el nivel de confianza.
            if adjusted_pnl < -(INITIAL_CAPITAL * 0.005):
                # Solo evaluamos si hay un cambio real para evitar spam
                persistence_handler.evaluate_performance(adjusted_pnl)
            
            is_small_cap = balance < 100
            
            # Check for AI Retraining
            check_auto_retrain()

            # --- [UNIVERSAL GUARDIAN v4.1: SYSTEM PROTECTION] ---
            # Re-instanciar o actualizar el guardián con el capital sincronizado
            if not guardian or guardian.initial_capital != INITIAL_CAPITAL:
                guardian = UniversalGuardian(INITIAL_CAPITAL, logger)
            
            guardian.update(equity)

            # --- [V3.7 KAIZEN LOCK DISABLED] ---
            # Omega Core no permite cierres dinámicos por equity floor.
            pass


                
            # --- PHASE 26: TELEGRAM PULSE (Heartbeat) ---
            if time.time() - last_pulse_time > 120: # Cada 2 minutos
                last_pulse_time = time.time()
                try:
                    if MT5_CONNECTED:
                        # 1. Obtener métricas
                        total_pnl = equity - balance
                        drawdown_pct = (acc.equity - daily_start_balance) / daily_start_balance * 100.0 if daily_start_balance > 0 else 0
                        weekly_peak = persistence_handler.state.get("weekly_equity_peak", equity)
                        
                        # 2. Calcular Objetivos
                        BASKET_CFG = {"threshold_pct": 2.0}
                        try:
                            with open("config/basket_config.json", "r") as f:
                                BASKET_CFG.update(json.load(f))
                        except: pass
                        target_usd = balance * (1 + BASKET_CFG["threshold_pct"] / 100.0)

                        # 3. Resumen de Distritos (L-H-N)
                        positions = active_positions # Ya cargadas arriba
                        block_pnl = {"ALFA": 0.0, "EXPL": 0.0, "NEME": 0.0, "WINNER": 0.0, "OTHER": 0.0}
                        if positions:
                            for p in positions:
                                profit = p.profit + getattr(p, 'swap', 0.0) + getattr(p, 'commission', 0.0)
                                comment = getattr(p, 'comment', "")
                                if "ALFA" in comment: block_pnl["ALFA"] += profit
                                elif "EXPL" in comment: block_pnl["EXPL"] += profit
                                elif "NEME" in comment: block_pnl["NEME"] += profit
                                elif "WINNER" in comment: block_pnl["WINNER"] += profit
                                else: block_pnl["OTHER"] += profit

                        distritos_text = (
                            f"🧬 *DISTRICTS PnL*\n"
                            f"├ ALFA: `{block_pnl['ALFA']:+.2f}`\n"
                            f"├ EXPL: `{block_pnl['EXPL']:+.2f}`\n"
                            f"├ NEME: `{block_pnl['NEME']:+.2f}`\n"
                            f"└ WINN: `{block_pnl['WINNER']:+.2f}`\n"
                        )

                        # 4. Mensaje Premium
                        msg = (
                            f"🏦 *STATUS PULSE OMEGA+*\n"
                            f"============================\n"
                            f"💰 *Balance:* `${balance:,.2f}`\n"
                            f"📈 *Equity:* `${equity:,.2f}`\n"
                            f"📊 *PnL Flotante:* `{total_pnl:+.2f}` (`{ (total_pnl/balance*100.0) if balance > 0 else 0:+.2f}%`)\n\n"
                            
                            f"{distritos_text}\n"
                            
                            f"🛡️ *Drawdown:* `{drawdown_pct:.2f}%` (Max -4.5%)\n"
                            f"🎯 *Obj. Basket:* `${target_usd:,.2f}`\n"
                            f"💎 *Pico Semanal:* `${weekly_peak:,.2f}`\n\n"
                            
                            f"Status: *OPERANDO* ⚡\n"
                            f"============================"
                        )
                        
                        if bot.enabled: 
                            bot.send_message(msg)
                            logger.info("💓 Premium Pulse Sent to Telegram")

                        # --- BASKET THEORY: SHADOW TELEMETRY ---
                        current_fingerprint = {f"{p.symbol}_{p.ticket}" for p in positions} if positions else set()
                        global basket_lifetime_peak, last_basket_fingerprint
                        
                        if current_fingerprint != last_basket_fingerprint:
                            # Basket changed (trade added or removed) -> Reset or Log Transition
                            if last_basket_fingerprint:
                                logger.info(f"📊 [BASKET_THEORY] Basket Changed. Previous Peak reached: ${basket_lifetime_peak:.2f}")
                            basket_lifetime_peak = 0.0
                            last_basket_fingerprint = current_fingerprint
                        
                        if positions:
                            current_basket_pnl = sum([p.profit + getattr(p, 'swap', 0.0) + getattr(p, 'commission', 0.0) for p in positions])
                            basket_lifetime_peak = max(basket_lifetime_peak, current_basket_pnl)
                            
                            # [v6.6.4] SECURE SHADOW TELEMETRY
                            from nanobot.utils.database import SecureDatabaseManager as db
                            log_entry = {
                                "time": datetime.now().isoformat(),
                                "pnl": round(current_basket_pnl, 4),
                                "peak": round(basket_lifetime_peak, 4),
                                "count": len(positions),
                                "equity": equity
                            }
                            db.append_log(BASKET_LOG, json.dumps(log_entry))
                                
                except Exception as e:
                    logger.error(f"Pulse/Telemetry Error: {e}")

            # --- [UNIVERSAL GUARDIAN v4.1: ACTIVE PROTECTIONS - EVERY ITERATION] ---
            # 1. Dynamic Profit Lock (Trinquete Escalonado) - DISABLED FOR PURITY
            profit_floor = guardian.get_profit_lock_floor(equity)
            if profit_floor and equity < profit_floor and active_pos_count > 0:
                pass # Disabled to allow individual TP/SL hits

            # 2. Hard Fuse Safety (Daily Limit) - DISABLED FOR PURITY
            # Disabled to allow individual TP/SL hits
            if INITIAL_CAPITAL >= 100:
                pass

            # 3. Harvest Mode (Pase de Cuenta) - DISABLED FOR PURITY
            # ONLY FOR FTMO CHALLENGES: Disabled to allow individual TP/SL hits
            if INITIAL_CAPITAL >= 100 and (equity >= INITIAL_CAPITAL * 1.10):
                pass
            logger.debug("--- [STEP 2] Pulse Checked ---")

            # --- PHASE 75: IRON SHIELD v2 (Active Guardian) ---
            if market_guardian is None and MT5_CONNECTED:
                market_guardian = MarketGuardian(mt5_client)
                logger.info("🛡️ IRON SHIELD v2: Market Guardian Initialized and Active.")
            
            if market_guardian:
                market_guardian.check_and_protect()
            
            # --- PHASE 75.1: BASKET PROFIT LOCK (Dynamic Security) ---
            check_basket_profit_lock(mt5_client, mt5_manager, bot)
            
            logger.debug("--- [STEP 3] Guardian Checked ---")

            # --- PHASE 76: ALL-WEATHER ORCHESTRATOR ---
            if orchestrator is None and MT5_CONNECTED and ORCHESTRATOR_ENABLED:
                orchestrator = BotOrchestrator(mt5_client=mt5_client)
                logger.info("🎼 ALL-WEATHER: Orchestrator Online. Regime detection active.")

            if meta_selector is None and META_SELECTOR_ENABLED:
                meta_selector = MetaRLSelector()
                logger.info("🧠 META-RL SELECTOR: Online. 3-Strategy experiment ready.")
            logger.debug("--- [STEP 4] Orchestrator/Selector Ready ---")

            # --- PHASE 75: IRON SHIELD v2 (Active Guardian) ---

            # --- PHASE 15: AI TRADE GUARDIAN ---
            try:
                logger.debug("--- [STEP 5] Management Start ---")
                manage_active_trades(bot_brain)
                logger.debug("--- [STEP 6] Management Completed ---")
            except Exception as e:
                import traceback
                logger.error(f"Guardian Error: {e}\n{traceback.format_exc()}")
            
            timestamp_str = datetime.now().strftime('%H:%M:%S')
            
            # --- PHASE 16: DYNAMIC RISK AUDIT (DEACTIVATED) ---
            # global last_risk_audit
            # if bot_brain and (time.time() - last_risk_audit > 3600):
            #     last_risk_audit = time.time()
            #     try:
            #         ctx = {
            #             'pairs_count': len(active_summary) if 'active_summary' in locals() else len(ASSET_MAP),
            #             'adx_threshold': 20,
            #             'avg_volatility': "Dynamic Audit"
            #         }
            #         assessment = bot_brain.assess_global_risk(ctx)
            #         AI_RISK_FACTOR = assessment.get('risk_factor', 1.0)
            #         risk_msg = assessment.get('reason', 'Market conditions stable.')
            #         print(f"\n🧠 AI RISK AUDIT: Factory={AI_RISK_FACTOR} | {risk_msg}")
            #         try:
            #             bot = TelegramBot()
            #             if bot.enabled:
            #                 bot.send_message(f"🧠 *AI RISK AUDIT*\nFactor: `{AI_RISK_FACTOR}`\nReason: _{risk_msg}_")
            #         except: pass
            #     except Exception as e:
            #         logger.error(f"Risk Audit Error: {e}")

            # --- 🛡️ FTMO IRON DOME: HARD-KILL SWITCH (v5.1.0) ---
            account_info = mt5_client.account_info()
            breaker_active = False
            
            if account_info:
                # 1. Calcular Balance Inicial del Día (Regla Prop Firm)
                today_midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                deals = mt5_client.history_deals_get(today_midnight, datetime.now())
                daily_pnl_closed = sum([d.profit + d.commission + d.swap for d in deals]) if deals else 0
                daily_start_balance = account_info.balance - daily_pnl_closed
                
                # 2. Calcular PnL Total (Equity Real vs Inicio del Día)
                total_daily_pnl = (account_info.equity - daily_start_balance)
                drawdown_pct = total_daily_pnl / daily_start_balance if daily_start_balance > 0 else 0
                
                # 3. Validar Violación de Regla (Límite 4.5% - Margen de Seguridad)
                if drawdown_pct <= -0.045:
                    msg = f"☠️ [FTMO IRON DOME ACTIVATED] Daily Drawdown reached {drawdown_pct*100:.2f}%. EMERGENCY SHUTDOWN."
                    logger.critical(msg)
                    mt5_manager.close_all_positions_atomic()
                    
                    # B. Apagar todas las estrategias en el Bridge
                    bridge_path = "dashboard_bridge.json"
                    if os.path.exists(bridge_path):
                        try:
                            with open(bridge_path, 'r') as f: bridge_data = json.load(f)
                            for p_key in bridge_data: bridge_data[p_key]["status"] = "OFF"
                            with open(bridge_path, 'w') as f: json.dump(bridge_data, f, indent=4)
                        except Exception as e: logger.error(f"Error disabling bridge: {e}")
                    
                    try:
                        from src.nanobot.utils.telegram_bot import TelegramBot
                        tg = TelegramBot()
                        if tg.enabled: tg.send_message(f"☠️ *FTMO IRON DOME*: Cuenta Blindada. DD: `{drawdown_pct*100:.2f}%`. Bot en HALT.")
                    except: pass
                    
                    circuit_breaker_cooldown = time.time() + 86400
                    breaker_active = True

                # --- 🚀 QUANTUM DYNAMIC FLOORS & TRAILING (v7.5.0) ---
                persistence_handler.validate_and_sync(account_info.balance, account_info.equity)
                
                total_floating_pnl = account_info.equity - account_info.balance
                floating_pct = (total_floating_pnl / account_info.balance) * 100.0 if account_info.balance > 0 else 0
                
                # Cargar Configuración de Cestas
                BASKET_CFG = {"threshold_pct": 2.0, "trailing_activation_pct": 1.2, "trailing_distance_pct": 0.5, "weekly_target_pct": 3.0, "weekly_floor_lock_pct": 1.0}
                try:
                    with open("config/basket_config.json", "r") as f:
                        BASKET_CFG.update(json.load(f))
                except: pass

                # A. LÓGICA DE TRAILING BASKET (Arrastre de Ganancias) - DISABLED FOR PURITY
                global CURRENT_BASKET_PEAK
                if len(active_positions) > 0:
                    pass # Basket tracking disabled to allow purely individual TP/SL hits
                else:
                    CURRENT_BASKET_PEAK = account_info.equity

                # B. LÓGICA DE SUELO SEMANAL (Weekly Glass Floor) - DISABLED FOR PURITY
                # Weekly floor removed to prevent interrupting trades mid-flight

                # C. Recovery Lock - DISABLED FOR PURITY
                # Recovery lock removed to allow statistical mapping of all levels

            # 4. Control de Cooldown Activo
            if time.time() < circuit_breaker_cooldown:
                breaker_active = True
                print(f"\r⏳ [COOLDOWN] FTMO Iron Dome / Breaker Activo. Gestión habilitada. Nuevas señales: BLOQUEADAS.", end="")
            
            print(f"\r⏳ Scanning... {timestamp_str} UTC | AI: {'ACTIVE' if stop_hunt_model else 'OFF'}", end="")
            sys.stdout.flush() # FORCE FLUSH for tail -f
            
            # --- PHASE 99: BASKET COOLDOWN (Anti-Carousel) ---
            global LAST_BASKET_RELEASE_TIME
            cooldown_period = 1800 # 30 minutes
            if time.time() - LAST_BASKET_RELEASE_TIME < cooldown_period:
                remaining = int(cooldown_period - (time.time() - LAST_BASKET_RELEASE_TIME))
                if remaining % 300 == 0: # Log every 5 mins
                    logger.info(f"⏳ [COOLDOWN] Basket Recently Locked. Skipping scanning for {remaining}s")
                time.sleep(5)
                continue

            # --- [RISK TRIBUNAL CYCLE RESET] ---
            if risk_tribunal:
                risk_tribunal.reset_cycle()
                # 1. Lectura del entorno
                active_positions = mt5_client.positions_get()
                if active_positions is None: active_positions = ()
                account_info = mt5_client.account_info()
                
                # Obtener el diccionario ATR para el Blindaje Némesis
                fallback_atr_dict = vol_engine.get_all_atrs() if vol_engine else {}
                
                # 2. Cálculo Forense de Riesgo Inicial
                base_global_risk = risk_tribunal.calculate_floating_risk(active_positions, account_info, fallback_atr_dict)
                available_cap = risk_tribunal.GLOBAL_CAP - base_global_risk
            else:
                available_cap = 0.025 # Fallback
            
            # --- [ALPHA SUPREMO PIPELINE V4.6.0] ---
            # 1. Cargar Configuración de Combate (ANTES de cualquier operación MT5)
            # La lectura de disco ocurre AQUÍ, lejos del Puente Silicon.
            tactical_config, requested_risk = load_tactical_config()
            # Sincronizar al cache global para que execute_signal no haga I/O propio
            global _last_tactical_config
            _last_tactical_config = tactical_config
            
            # 2. ESCUDO DE SEGURIDAD: Sincronización y Blindaje de Riesgo
            HARD_LIMIT_RISK = 0.02 # 2.0% (Límite Institucional FTMO/Prop)
            if requested_risk > HARD_LIMIT_RISK:
                logger.error(f"🚨 [SECURITY OVERRIDE] Riesgo solicitado ({requested_risk*100:.1f}%) excede el límite de seguridad. Ajustado a 2.0%")
                RISK_PER_TRADE = HARD_LIMIT_RISK
            else:
                if requested_risk != RISK_PER_TRADE:
                    logger.info(f"⚙️ [RISK UPDATE] Pelotón sincronizado a {requested_risk*100:.2f}% de riesgo.")
                RISK_PER_TRADE = requested_risk

            signal_pool = []
            for pair in ASSET_MAP.keys():
                # --- [INCISION OMEGA+: DASHBOARD SENSOR] ---
                pair_settings = tactical_config.get(pair, {"status": "ON", "strategy_mode": "AUTO"})
                
                if pair_settings["status"] == "OFF":
                    logger.info(f"⚪ [DASHBOARD] {pair} está en OFF. Saltando análisis.")
                    continue
                    
                # --------------------------------------------
                forced_role = None
                if pair_settings.get("strategy_mode") == "MANUAL":
                    forced_role = pair_settings.get("manual_nem_role")
                    if forced_role:
                        logger.warning(f"🎯 [DASHBOARD OVERRIDE] Forzando {pair} a {forced_role}")

                symbol = ASSET_MAP.get(pair)
                data = get_mt5_data(symbol, bars=200)
                if data.empty or len(data) < 50: continue
                
                # --- [NEME FIX] INYECTAR INDICADORES ---
                data = calculate_core_indicators(data)
                
                if STRATEGY_HUB_ENABLED and STRATEGY_HUB:
                    # Get signal from StrategyHub (returns SignalResult, not list)
                    hub_result = STRATEGY_HUB.get_signal(pair, data, mode=forced_role)
                    if hub_result.signal != 0:
                        dir_str = "BUY" if hub_result.signal == 1 else "SELL"
                        logger.info(f"📡 [RAW ALPHA] {pair}: {hub_result.strategy} ({hub_result.source}) suggests {dir_str}. Entering Pool.")
                        signal_pool.append(AlphaSignal(
                            symbol=pair, 
                            direction=hub_result.signal,
                            confidence=0.75,  # Default confidence from StrategyHub
                            strategy_tag=hub_result.strategy,
                            edge_type="TREND",
                            suggested_rr=hub_result.recommended_rr,
                            regime="TREND"
                        ))
                signal_pool = run_iron_funnel_arbitration(pair, data, signal_pool)
            if signal_pool:
                signal_pool.sort(key=lambda x: x.confidence, reverse=True)
                unique_symbols = set()
                global mega_grid_tracker
                if mega_grid_tracker is None: mega_grid_tracker = MegaGridTracker(mt5_client, logger)
                for signal in signal_pool:
                    if signal.symbol not in unique_symbols:
                        # --- [TRIBUNAL DE JUSTICIA CAPITAL] ---
                        # Cargar el Alpha Heat Map (affinity_map)
                        try:
                            with open(AFFINITY_MAP_PATH, "r") as f:
                                affinity_data = json.load(f)
                            symbol_data = affinity_data.get(signal.symbol, {})
                        except:
                            symbol_data = {}
                        
                        # Obtener datos de entorno para el Tribunal V9.0
                        now = datetime.now()
                        curr_hour = now.hour
                        
                        # Spread y ATR
                        tick = mt5_client.symbol_info_tick(signal.symbol)
                        sym_inf = mt5_client.symbol_info(signal.symbol)
                        current_spread = (tick.ask - tick.bid) / sym_inf.point if tick and sym_inf else None
                        atr_pips = vol_engine.get_symbol_atr_pips(signal.symbol) if vol_engine else None

                        # Pasar por el Tribunal
                        final_risk_pct = risk_tribunal.get_meritocratic_risk(
                            symbol=signal.symbol,
                            symbol_data=symbol_data,
                            base_risk=RISK_PER_TRADE, 
                            available_cap=available_cap,
                            current_hour=curr_hour,
                            current_spread_pips=current_spread,
                            symbol_atr_pips=atr_pips,
                            stasis=is_stasis
                        )
                        
                        # Freno de mano final
                        if final_risk_pct < 0.0005: # < 0.05%
                            logger.warning(f"🚫 [RISK TRIBUNAL] {signal.symbol} rejected: Insufficient risk budget or merit.")
                            continue

                        # --- [v10.0.0] OMEGA CORE: DISTRIBUCIÓN ASIMÉTRICA DEL 1% ---
                        # Consultamos el VitalityOracle para saber qué nivel merece capital real
                        try:
                            acc_for_omega = mt5_client.account_info()
                            equity_for_omega = float(acc_for_omega.equity) if acc_for_omega else current_capital
                            # Determinar el rol activo del símbolo
                            _omega_role = "NEM2" if "Antith" in symbol_data.get("reco", "") else "NEM1"
                            omega_allocation = risk_tribunal.get_omega_core_allocation(
                                symbol=signal.symbol,
                                role=_omega_role,
                                account_equity=equity_for_omega,
                                max_risk_pct=0.01  # 1% global
                            )
                            # Inyectar la distribución en la señal para que execute_signal la use
                            signal._omega_level_risks = omega_allocation["level_risks"]
                            signal._omega_health      = omega_allocation["health"]
                            signal._omega_scout_only  = omega_allocation["scout_only"]

                            # Si el sistema está en COMA, bloquear (además del Tribunal individual)
                            if omega_allocation["scout_only"] and not is_stasis:
                                logger.warning(f"🧬 [OMEGA CORE] {signal.symbol}: Sistema en modo Biopsia. Desplegando Grid Mínimo (0.01) para mapeo estadístico.")
                                # signal.force_scout = True # DISABLED: Allow 7 levels for statistical purity
                        except Exception as e_omega:
                            logger.warning(f"⚠️ [OMEGA CORE] Fallo en diagnóstico, usando distribución legacy: {e_omega}")
                            signal._omega_level_risks = None

                        # Ejecutar señal pasándole el riesgo ajustado
                        mega_grid_tracker.execute_signal(signal, risk_pct=final_risk_pct)
                        unique_symbols.add(signal.symbol)
                        
                        # Comprometer en la memoria de tránsito
                        risk_tribunal.commit_risk(final_risk_pct)

            # --- UPDATE LHN REAL GRID (Check tickets) ---
            if MT5_CONNECTED:
                virtual_manager.update()
                    
            time.sleep(1) # Fast scan
            
        except KeyboardInterrupt:
            print("\n🛑 Stopped.")
            if MT5_CONNECTED: mt5_client.shutdown()
            break
        except Exception as e:
            logger.error(f"Loop error: {e}")
            # time.sleep(60)
            break # Break and restart for clean state if needed

def nightly_polimata_retrain():
    import subprocess
    while True:
        try:
            now = datetime.now()
            target = now.replace(hour=23, minute=55, second=0, microsecond=0)
            if now > target:
                target += timedelta(days=1)
            sleep_seconds = (target - now).total_seconds()
            
            logger.info(f"🧠 Next Polimata sleep cycle in {sleep_seconds/3600:.1f} hrs")
            time.sleep(sleep_seconds)
            
            logger.info("🧠 POLIMATA REM SLEEP INITIATED (Auto-Retraining)...")
            if bot.enabled: bot.send_message("🧠 *Polimata REM Sleep*\nInitiating daily data assimilation...")
            
            # Execute retraining script
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "retrain_polimata.py")
            subprocess.run([sys.executable, script_path], check=True)
            
            # Reload Model
            global polimata_model
            if os.path.exists(POLIMATA_MODEL_PATH):
                from stable_baselines3 import DQN
                polimata_model = DQN.load(POLIMATA_MODEL_PATH)
                logger.info("🧠 POLIMATA WOKE UP. Neural weights updated.")
                if bot.enabled: bot.send_message("🧠 *Polimata Woke Up*\nNeural weights successfully updated.")
                
        except Exception as e:
            logger.error(f"⚠️ Error in Polimata REM Sleep: {e}")
            time.sleep(3600)  # Sleep an hour before retrying on crash

if __name__ == "__main__":
    # import threading
    # polimata_thread = threading.Thread(target=nightly_polimata_retrain, daemon=True)
    # polimata_thread.start()
    main()
