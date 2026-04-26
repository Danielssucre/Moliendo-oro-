#!/usr/bin/env python3
"""
NANOBOT LIVE TRADING RUNNER (v2.0 Clean)
- Strategy: HIVE V5 (Trend Sniper)
- ML Modules: Gatekeeper (Shadow), StopHunt (Active), RL Trailing (Active)
- Risk: Dynamic Institutional w/ Kelly Sizing
"""

# --- V3.8 INSTITUTIONAL BODY ---
class AlphaSignal:
    def __init__(self, symbol, direction, confidence, strategy_tag, edge_type, suggested_rr, regime):
        self.symbol, self.direction, self.confidence = symbol, direction, confidence
        self.strategy_tag, self.edge_type, self.suggested_rr, self.regime = strategy_tag, edge_type, suggested_rr, regime
        self.force_scout = False

def run_iron_funnel_arbitration(pair, data, signal_pool):
    is_volatile = any(k in pair.upper() for k in ["XAU", "XAG", "BTC", "ETH", "SOL"])
    force_scout = (is_volatile and INITIAL_CAPITAL < 100000)
    # El log solo se dispara si hay señales reales siendo arbitradas
    for s in signal_pool:
        if s.symbol == pair and force_scout: 
            s.force_scout = True
            logger.info(f"⚖️ [IRON FUNNEL] Signal {s.strategy_tag} on {pair} forced to SCOUT mode (0.01 lot).")
    return signal_pool

class MegaGridTracker:
    def __init__(self, mt5_client, logger):
        self.client, self.logger = mt5_client, logger
        
    def execute_signal(self, signal):
        from src.nanobot.strategies.mega_grid_v2 import MegaGridV2
        global RISK_PER_TRADE, current_capital, ASSET_MAP
        
        # 0. Cargar Configuración Táctica Localizada
        pair = signal.symbol
        tactical_config, _ = load_tactical_config() # Solo por si hubo cambio de rol manual
        pair_settings = tactical_config.get(pair, {"strategy_mode": "AUTO"})
        
        # 1. DETERMINAR ROL (NEM1/NEM2)
        # Prioridad: Override Manual > Dirección de Señal
        nem_type = "NEM1" if signal.direction == 1 else "NEM2"
        if pair_settings.get("strategy_mode") == "MANUAL":
            nem_type = pair_settings.get("manual_nem_role", nem_type)
            self.logger.warning(f"🎯 [DASHBOARD OVERRIDE] Usando Rol manual: {nem_type} para {pair}")

        # 2. INICIALIZAR ESTRATEGIA MEGAGRID
        strategy = MegaGridV2()
        symbol_mt5 = ASSET_MAP.get(pair, pair)
        
        # Obtener ATR actual para el espaciado (v4.2.5 scalar fix)
        data = get_mt5_data(symbol_mt5, bars=100)
        if not data.empty:
            atr_series = calculate_atr(data)
            # Usamos el antepenúltimo valor cerrado para evitar ruido de vela viva
            atr_val = float(atr_series.iloc[-2]) if len(atr_series) > 2 else 0.00100
        else:
            atr_val = 0.00100
            
        entry_price = mt5_client.symbol_info_tick(symbol_mt5).ask if signal.direction == 1 else mt5_client.symbol_info_tick(symbol_mt5).bid

        # 3. GENERAR POOL DE 7 NIVELES (El corazón OMEGA+)
        is_scout = getattr(signal, 'force_scout', False)
        levels = strategy.generate_pool(
            symbol=symbol_mt5,
            entry_price=entry_price,
            atr=atr_val,
            direction=signal.direction,
            total_risk=RISK_PER_TRADE, # El valor sincronizado con el Dashboard
            is_scout=is_scout,
            nem_type=nem_type
        )

        # 4. EJECUCIÓN ATÓMICA
        self.logger.info(f"🚀 [MEGAGRID DISPATCH] Desplegando {len(levels)} niveles para {pair} (Riesgo: {RISK_PER_TRADE*100:.2f}%)")
        
        for level in levels:
            # Cálculos matemáticos de precisión OMEGA+
            nem_side = level['side']
            sl_dist = atr_val * level['sl_mult']
            tp_dist = sl_dist * level['rr']
            
            # Precios de Salida
            if nem_side == 1: # BUY
                sl_price = level['entry'] - sl_dist
                tp_price = level['entry'] + tp_dist
            else: # SELL
                sl_price = level['entry'] + sl_dist
                tp_price = level['entry'] - tp_dist
                
            # Cálculo de lotaje preciso basado en balance real
            risk_usd = current_capital * level['risk_pct']
            
            # Obtener el valor del Pip/Tick del símbolo para lotaje exacto
            symbol_info = mt5_client.symbol_info(symbol_mt5)
            point = symbol_info.point if symbol_info else 0.0001
            sl_pips = sl_dist / (point * 10) if point < 0.01 else sl_dist / point
            sl_pips = max(1.0, sl_pips) # Evitar división por cero
            
            # Fórmula Institucional: Lote = Riesgo $ / (Pips * Valor_Pip)
            # Simplificado: 1 lote estándar = $10/pip en Forex
            lot_size = (risk_usd / (sl_pips * 10))
            lot_size = max(0.01, round(lot_size, 2))

            trade_dir = "BUY" if nem_side == 1 else "SELL"
            comment = f"{signal.strategy_tag}_{nem_type}_{'SCOUT' if is_scout else 'HEAVY'}_L{level['level']}"
            
            execute_mt5_trade(
                symbol_mt5, 
                trade_dir, 
                level['entry'], 
                sl_price, 
                tp_price, 
                lot_size, 
                comment=comment
            )
            
            # Cadencia Institucional (v4.4.0): Máxima resiliencia para macOS
            time.sleep(1.0)

        # 5. DESPACHO INVERSO (EL ESPÍA SCOUT DE COBERTURA)
        if not is_scout:
            spy_role = "NEM1" if nem_type == "NEM2" else "NEM2"
            spy_dir = "SELL" if trade_dir == "BUY" else "BUY"
            spy_comment = f"{signal.strategy_tag}_{spy_role}_SPY"
            
            self.logger.info(f"🕵️ [INVERSE SPY] Dispatching coverage: {spy_comment}")
            execute_mt5_trade(symbol_mt5, spy_dir, 0, 0, 0, 0.01, comment=spy_comment)


import sys
import os
import time
import logging
import json
import pandas as pd
import numpy as np
from datetime import datetime

# Silenciador de Telemetría (v4.5.0)
LAST_TELEGRAM_ERROR_TIME = 0
TELEGRAM_ERROR_COOLDOWN = 60 # 1 minuto entre reportes de error repetitivos

# --- ALPHA SUPREMO HUB INFRASTRUCTURE (GLOBAL SCOPE) ---
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

STRATEGY_HUB_ENABLED = True
STRATEGY_HUB = None
mega_grid_tracker = None
GLOBAL_RESUME_TIME = 0

# Initialize StrategyHub early
try:
    from src.nanobot.strategies.strategy_hub import StrategyHub
    STRATEGY_HUB = StrategyHub()
    print("✅ STRATEGY HUB (ForexInfantry + CryptoLab) initialized")
except Exception as e:
    print(f"❌ STRATEGY HUB init failed: {e}")
    STRATEGY_HUB_ENABLED = False

import threading
from datetime import datetime, timedelta, timezone

# --- LOGGING SETUP ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from src.nanobot.utils.telegram_bot import TelegramBot
except ImportError:
    class TelegramBot: # Fallback dummy
        enabled = False
        def send_message(self, msg): print(f"TELEGRAM MOCK: {msg}")

from src.nanobot.ml.stop_hunt import StopHuntModel
ML_ENABLED = True

try:
    from src.nanobot.strategies.skypie_enel import SkypieEnel
    ENEL_ENGINE = SkypieEnel()
    ENEL_ENABLED = True
except ImportError:
    ENEL_ENABLED = False
    print("⚠️ Skypie-Enel strategy module not found.")

try:
    from src.nanobot.strategies.hunter_x import HunterX
    HUNTER_X_ENGINE = HunterX()
    HUNTER_X_ENABLED = True
except ImportError:
    HUNTER_X_ENABLED = False
    print("⚠️ Hunter X strategy module not found.")

try:
    from src.nanobot.kelly_sizing import BayesianEnsemble as BayesianBeliefEngine
    BAYES_ENABLED = True
except ImportError:
    try:
        from src.nanobot.kelly_sizing import KellyBeliefEngine
        BAYES_ENABLED = True
    except:
        BAYES_ENABLED = False
        print("⚠️ Kelly Module missing.")

try:
    from src.nanobot.ml.rl_trailing import RLTrailingManager
    RL_AGENT_ENABLED = True
except Exception as e:
    RL_AGENT_ENABLED = False
    print(f"⚠️ RL Trailing disabled (torch not found): {e}")
    class RLTrailingManager: pass  # Stub

try:
    from src.nanobot.ml.mfe_sniper import MFESniperManager
    SNIPER_ENABLED = True
except Exception as e:
    SNIPER_ENABLED = False
    print(f"⚠️ MFE Sniper disabled (torch not found): {e}")
    class MFESniperManager: pass  # Stub

try:
    from src.nanobot.ml.risk_oracle import AsymmetricRiskOracle
    RISK_ORACLE_ENABLED = True
except Exception as e:
    RISK_ORACLE_ENABLED = False
    print(f"⚠️ Risk Oracle disabled: {e}")
    class AsymmetricRiskOracle: pass  # Stub

try:
    from src.nanobot.orchestrator import BotOrchestrator
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
    from src.nanobot.ml.meta_rl_selector import MetaRLSelector
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

    # 2. Leer Riesgo Maestro (Config 8000)
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                cfg = json.load(f)
                global_risk = cfg.get("risk_management", {}).get("risk_per_trade", 0.004)
        except: pass

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
                res = self.client.order_send(request)
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
                    self.client.order_send(cancel_req)
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
                res = self.client.order_send(request)
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
                # Bridge is up but terminal might be dead
                return False
            return True
        except:
            print("⚠️ Connection lost! Reconnecting...")
            self.connected = False
            MT5_CONNECTED = False
            return self.connect(max_retries=3)

def check_basket_profit_lock(mt5_client, mt5_manager, bot):
    """Checks if the combined floating profit exceeds the threshold and closes all if enabled."""
    global LAST_BASKET_ENABLED, LAST_BASKET_THRESHOLD
    
    config_path = "config/basket_config.json"
    if not os.path.exists(config_path):
        return
        
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        enabled = config.get("enabled", False)
        threshold = config.get("threshold", 5.0)
        
        # --- CHANGE DETECTION LOGGING ---
        if enabled != LAST_BASKET_ENABLED or threshold != LAST_BASKET_THRESHOLD:
            status_str = "ON" if enabled else "OFF"
            logger.info(f"🔍 [SYNC] Basket Lock: {status_str} | TP Target: ${threshold:.2f}")
            LAST_BASKET_ENABLED = enabled
            LAST_BASKET_THRESHOLD = threshold
            
        if not enabled:
            return
        
        acc = mt5_client.account_info()
        if acc:
            floating_pnl = float(acc.profit)
            global CURRENT_BASKET_PEAK, CURRENT_BASKET_FLOOR
            
            # --- PEAK TRACKING ---
            if floating_pnl > CURRENT_BASKET_PEAK:
                CURRENT_BASKET_PEAK = floating_pnl
                
            # --- DYNAMIC FLOOR LOGIC (Anti-Fuga) ---
            if CURRENT_BASKET_PEAK >= 4.50:
                if CURRENT_BASKET_FLOOR < 2.50:
                    logger.info(f"🛡️ [TRAIL] Profit was $4.50+. Safety Floor ARMED at $2.50")
                    CURRENT_BASKET_FLOOR = 2.50
            elif CURRENT_BASKET_PEAK >= 3.00:
                if CURRENT_BASKET_FLOOR < 1.00:
                    logger.info(f"🛡️ [TRAIL] Profit was $3.00+. Safety Floor ARMED at $1.00")
                    CURRENT_BASKET_FLOOR = 1.00
            
            # --- TRIGGER: TARGET OR FLOOR ---
            force_close = False
            close_reason = ""
            
            if floating_pnl >= threshold:
                force_close = True
                close_reason = f"Target Reached (${floating_pnl:.2f} >= ${threshold:.2f})"
            elif floating_pnl < CURRENT_BASKET_FLOOR:
                force_close = True
                close_reason = f"Trailing Floor Hit (${floating_pnl:.2f} < ${CURRENT_BASKET_FLOOR:.2f})"
                
            if force_close:
                logger.warning(f"🎯 [BASKET LOCK] {close_reason}. Securing gains.")
                if bot.enabled:
                    bot.send_message(f"🎯 *BASKET LOCKING*\nReason: `{close_reason}`\nClosing all positions...")
                
                mt5_manager.close_all_positions()
                
                # --- RESET BASKET STATE ---
                CURRENT_BASKET_PEAK = 0.0
                CURRENT_BASKET_FLOOR = -999.0
                
                # --- COOLDOWN FIX (0.2.0) ---
                global LAST_BASKET_RELEASE_TIME
                time.sleep(5) # Let MT5 sync the closure
                LAST_BASKET_RELEASE_TIME = time.time()
                
                # Log trigger time back to config
                config["last_trigger"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=4)
                    
    except Exception as e:
        logger.error(f"Error in Basket Profit Lock: {e}")

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
        Called in the main loop to evaluate if it's Friday afternoon.
        """
        if not self.mt5: return
        
        est_now = self.get_est_time()
        is_friday = est_now.weekday() == 4
        
        if not is_friday: return
        
        # 3:45 PM EST (15:45) is the start of the Smart Close window
        if (est_now.hour == 15 and est_now.minute >= 45) or est_now.hour == 16:
            positions = self.mt5.positions_get()
            if not positions: return
            
            for p in positions:
                if self.is_crypto(p.symbol): continue
                
                profit = p.profit
                
                # SMART CLOSE: If in profit after 4:00 PM, close immediately to secure it.
                if profit > 0:
                    logger.info(f"🛡️ IRON SHIELD v2 (SMART): Closing {p.symbol} in profit (${profit:.2f}) before weekend.")
                    self._close_position(p)
                
                # HARD LIMIT: If it's after 3:55 PM (5 mins before close), close regardless of P/L.
                elif (est_now.hour == 15 and est_now.minute >= 55) or est_now.hour == 16:
                    logger.warning(f"🛡️ IRON SHIELD v2 (HARD): Forced closure of {p.symbol} (${profit:.2f}) to prevent weekend GAP.")
                    self._close_position(p)

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
        
        res = self.mt5.order_send(request)
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


def execute_mt5_trade(pair, order_type_str, price, sl, tp, volume, comment="Nanobot HIVE V5"):
    """
    Phase 71: Execute Pending Order on Silicon MT5
    """
    if not MT5_CONNECTED: return
    
    symbol_mt5 = MT5_SYMBOL_MAP.get(pair, pair) # Fallback to pair if not in map
    
    # [NEW v4.4.0] FORCE SYMBOL AWAKE
    # Ensures symbol is in Market Watch to prevent terminal timeouts.
    if not mt5_client.symbol_select(symbol_mt5, True):
        logger.error(f"❌ Impossible to select/awake symbol: {symbol_mt5}")
        return None

    # [NEW] ENSURE SYMBOL LOCK (Extreme Survival)
    # Prevent duplicate exposure for the same symbol in active or pending orders.
    if not check_correlation_exposure(pair, order_type_str):
        return None
    
    # Check Spread & Tick
    info = mt5_client.symbol_info(symbol_mt5)
    tick = mt5_client.symbol_info_tick(symbol_mt5)
    if not info or not tick:
        logger.error(f"❌ Symbol Info/Tick Failed: {symbol_mt5}")
        return
        
    # Phase 3: Universal Pip/Point Logic
    pip_val = info.point 
    # For Forex, 1 pip = 10 points usually. For Gold/Crypto, point is usually the min tick.
    # We use a standard "Institutional Pip" for spread display, but info.point for buffer.
    pips_in_point = 10 if ("USD" in pair and "JPY" not in pair and "XAU" not in pair and "BTC" not in pair) else 1
    
    buffer_val = PENDING_ORDER_BUFFER_PIPS * info.point * pips_in_point
    filling_mode = get_filling_mode(info)
    
    # Phase 4 Logic Hardening: Respect Technical Price
    # Calculate Distances based on the technical signal price 'price'
    sl_dist = abs(price - sl)
    tp_dist = abs(price - tp)
    
    if "BS" in order_type_str:
        # Ensure pending order is at least buffer_val above current Ask
        target_price = max(price, tick.ask + buffer_val)
        sl = target_price - sl_dist
        tp = target_price + tp_dist
    else:
        # Ensure pending order is at least buffer_val below current Bid
        target_price = min(price, tick.bid - buffer_val)
        sl = target_price + sl_dist
        tp = target_price - tp_dist
        
    price = target_price

    # Check Live Spread
    # Use native points for spread calculation to avoid hardcoded pip mismatches
    live_spread_points = (tick.ask - tick.bid) / info.point
    
    # Define max spread in points (Phase 3: Conservative for Forex, relaxed for Crypto/Gold)
    max_spread_points = 50 # Default 5 pips / 50 points
    if "BTC" in pair or "ETH" in pair: max_spread_points = 1000 # Relaxed for Crypto
    if "XAU" in pair: max_spread_points = 100 # Relaxed for Gold ($1.00 spread max)

    if live_spread_points > max_spread_points:
        logger.warning(f"⚠️ SPREAD HIGH for {pair}: {live_spread_points:.1f} > {max_spread_points} points")
        return

    # Check Stops Level (Minimum distance)
    stops_level = info.trade_stops_level * info.point
    min_dist = stops_level * 1.5 # Safety Factor
    
    if "BS" in order_type_str:
        if abs(price - tick.ask) < min_dist:
            logger.info(f"⚠️ PRICE TOO CLOSE: Adjusting BS to Min Dist ({min_dist:.5f})")
            price = tick.ask + min_dist
    else:
        if abs(price - tick.bid) < min_dist:
            logger.info(f"⚠️ PRICE TOO CLOSE: Adjusting SS to Min Dist ({min_dist:.5f})")
            price = tick.bid - min_dist

    # --- NORMALIZATION ---
    # 1. Volume
    step_vol = info.volume_step
    if step_vol > 0:
        volume = round(volume / step_vol) * step_vol
    
    if volume < info.volume_min: volume = info.volume_min
    if volume > info.volume_max: volume = info.volume_max
    volume = round(volume, 2)
    
    # 2. Price
    price = round(price, info.digits)
    sl = round(sl, info.digits)
    tp = round(tp, info.digits)
    
    logger.info(f"🤖 [FINAL_VERIFICATION] {pair}: {volume:.2f} lots @ {price:.5f}")
    
    action = mt5_client.TRADE_ACTION_PENDING
    if "BS" in order_type_str:
        if price <= tick.ask:
            # If price is already at or below Ask, use BUY LIMIT or MARKET
            # For HIVE, we stay Conservative: Buy Limit if below, Market if at
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
        "comment": str(comment),
    }
    
    max_trade_retries = 2
    for attempt in range(max_trade_retries):
        try:
            result = mt5_client.order_send(request)
            
            # Blindaje de Seguridad v4.5.1: Validar respuesta del terminal con re-intento
            if result is None:
                if attempt == 0:
                    err_msg = f"❌ TERMINAL TIMEOUT (Intento 1): RE-SINCRONIZANDO puente Silicon para {pair}..."
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
                df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
                tr = pd.concat([df['high']-df['low'], abs(df['high']-df['close'].shift(1)), abs(df['low']-df['close'].shift(1))], axis=1).max(axis=1)
                df['atr'] = tr.rolling(14).mean()
                atr = df['atr'].iloc[-1]
            else:
                atr = 0.002 # Fallback
                df = pd.DataFrame()
            
            # 🎯 DANIEL'S PARTIAL EXIT (1.3R): 50% Close + Move to BE
            entry_p = p.price_open
            tp_p = p.tp
            
            # Calculate Initial Risk with BATCHED deals
            initial_risk_pips = get_initial_risk_pips(p.ticket, symbol, entry_p, info.point, pre_fetched_deals=all_deals)
            
            if not initial_risk_pips:
                tp_dist_pips = abs(tp_p - entry_p) / info.point if tp_p > 0 else (p.price_current * 0.003 / info.point)
                initial_risk_pips = tp_dist_pips / 1.5
                
            if initial_risk_pips < 1.0: initial_risk_pips = 10.0
            
            current_pips = (p.price_current - entry_p) / info.point
            r_multiple = current_pips / initial_risk_pips if p.type == 0 else (-current_pips / initial_risk_pips)
            
            MAX_TRADE_HOURS = 96.0 if symbol == "BTCUSD" else 72.0
            MIN_R_TO_SKIP_BE = 0.5
            duration_hours = (datetime.now() - datetime.fromtimestamp(p.time)).total_seconds() / 3600
            
            if duration_hours > MAX_TRADE_HOURS and r_multiple < MIN_R_TO_SKIP_BE:
                be_offset_points = max(10, info.trade_stops_level + 5)
                be_price = entry_p + (be_offset_points * info.point) if p.type == 0 else entry_p - (be_offset_points * info.point)
                sl_already_at_be = (p.type == 0 and p.sl >= be_price) or (p.type == 1 and p.sl <= be_price and p.sl > 0)

                if not sl_already_at_be:
                    logger.warning(f"⏰ TIEMPO MAX ({duration_hours:.1f}h): {symbol} #{p.ticket} no ha llegado a 0.5R ({r_multiple:.2f}R). Moviendo SL a BE.")
                    sl_request = {
                        "action": int(mt5_client.TRADE_ACTION_SLTP),
                        "symbol": str(symbol),
                        "sl": float(be_price),
                        "tp": float(p.tp),
                        "position": int(p.ticket)
                    }
                    mt5_client.order_send(sl_request)
            
            # Partial Exit check
            is_partialed = "PARTIAL" in p.comment or "MFE" in p.comment or "SNIPER" in p.comment
            if hasattr(p, 'volume_initial') and p.volume < p.volume_initial:
                is_partialed = True

            if SNIPER_ENABLED and sniper_manager and not is_partialed:
                action = sniper_manager.process_position(p, info, df, mt5_client=mt5_client)
                if action == "PARTIAL" or r_multiple >= 1.5:
                    reason = "AI SNIPER" if action == "PARTIAL" else "SAFETY 1.3R"
                    print(f"🎯 PARTIAL EXIT TRIGGERED ({reason}): Closing 50% of {symbol} (#{p.ticket}).")
                    partial_vol = p.volume / 2.0
                    if info.volume_step > 0:
                        partial_vol = round(partial_vol / info.volume_step) * info.volume_step
                    if partial_vol < info.volume_min: partial_vol = p.volume
                    partial_vol = round(partial_vol, 2)
                    
                    tick = mt5_client.symbol_info_tick(symbol)
                    close_request = {
                        "action": int(mt5_client.TRADE_ACTION_DEAL),
                        "symbol": str(symbol),
                        "volume": float(partial_vol),
                        "type": int(mt5_client.ORDER_TYPE_SELL if p.type == 0 else mt5_client.ORDER_TYPE_BUY),
                        "position": int(p.ticket),
                        "price": float(tick.bid if p.type == 0 else tick.ask),
                        "comment": str(f"MFE SNIPER {reason}"),
                        "type_filling": int(get_filling_mode(info)),
                    }
                    mt5_client.order_send(close_request)
                    
                    be_offset = max(10, info.trade_stops_level + 5)
                    new_sl = entry_p + (be_offset * info.point) if p.type == 0 else entry_p - (be_offset * info.point)
                    sl_request = {
                        "action": int(mt5_client.TRADE_ACTION_SLTP),
                        "symbol": str(symbol),
                        "sl": float(new_sl),
                        "tp": float(p.tp),
                        "position": int(p.ticket)
                    }
                    mt5_client.order_send(sl_request)

            # Kaido Trailing
            if "KAIDO" in p.comment:
                new_target_sl = None
                if r_multiple >= 3.0:
                    new_target_sl = entry_p + (initial_risk_pips * 2.0 * info.point) if p.type == 0 else entry_p - (initial_risk_pips * 2.0 * info.point)
                elif r_multiple >= 2.0:
                    new_target_sl = entry_p + (initial_risk_pips * 1.0 * info.point) if p.type == 0 else entry_p - (initial_risk_pips * 1.0 * info.point)
                elif r_multiple >= 1.2:
                    new_target_sl = entry_p + (initial_risk_pips * 0.5 * info.point) if p.type == 0 else entry_p - (initial_risk_pips * 0.5 * info.point)
                elif r_multiple >= 0.6:
                    be_offset = max(10, info.trade_stops_level + 5)
                    new_target_sl = entry_p + (be_offset * info.point) if p.type == 0 else entry_p - (be_offset * info.point)
                
                if new_target_sl:
                    should_move = (p.type == 0 and new_target_sl > p.sl) or (p.type == 1 and (new_target_sl < p.sl or p.sl == 0))
                    if should_move:
                        sl_request = {
                            "action": int(mt5_client.TRADE_ACTION_SLTP),
                            "symbol": str(symbol),
                            "sl": float(new_target_sl),
                            "tp": float(p.tp),
                            "position": int(p.ticket)
                        }
                        mt5_client.order_send(sl_request)

            active_summary.append({
                'ticket': int(p.ticket),
                'symbol': symbol,
                'type': int(p.type),
                'profit_pips': float(p.profit),
                'duration_hours': duration_hours
            })
            
            # RL Infinite Runner
            if RL_AGENT_ENABLED and rl_manager and is_partialed:
                if 'df' in locals() and not df.empty:
                    action_rl = rl_manager.process_position(p, info, df, mt5_client=mt5_client)
                    if action_rl == "MOVE":
                        new_sl = p.sl + (initial_risk_pips * 0.3 * info.point) if p.type == 0 else p.sl - (initial_risk_pips * 0.3 * info.point)
                        sl_request = {
                            "action": int(mt5_client.TRADE_ACTION_SLTP),
                            "symbol": str(symbol),
                            "sl": float(new_sl),
                            "tp": float(p.tp),
                            "position": int(p.ticket)
                        }
                        mt5_client.order_send(sl_request)
                    elif action_rl == "CLOSE":
                        tick = mt5_client.symbol_info_tick(symbol)
                        close_req = {
                            "action": int(mt5_client.TRADE_ACTION_DEAL),
                            "symbol": str(symbol),
                            "volume": float(p.volume),
                            "type": int(mt5_client.ORDER_TYPE_SELL if p.type == 0 else mt5_client.ORDER_TYPE_BUY),
                            "position": int(p.ticket),
                            "price": float(tick.bid if p.type == 0 else tick.ask),
                            "comment": "RL AGENT CLOSE",
                            "type_filling": int(get_filling_mode(info)),
                        }
                        mt5_client.order_send(close_req)
        except Exception as e:
            logger.error(f"Error managing position {p.symbol if 'p' in locals() else 'unknown'}: {e}")

    # 🧠 AI Audit (Every 30 minutes)
    if bot_brain and (current_time - last_trade_audit > 1800):
        last_trade_audit = current_time
        print("🧠 AI GUARDIAN: Auditing active positions...")
        recommendations = bot_brain.audit_trade_health(active_summary)
        for rec in recommendations:
            ticket_audit = int(rec.get('ticket', 0))
            action_audit = rec.get('action')
            reason_audit = rec.get('reason')
            if action_audit == "CLOSE" and ticket_audit > 0:
                pos = next((p for p in positions if p.ticket == ticket_audit), None)
                if pos:
                    tick = mt5_client.symbol_info_tick(pos.symbol)
                    request_audit = {
                        "action": int(mt5_client.TRADE_ACTION_DEAL),
                        "symbol": str(pos.symbol),
                        "volume": float(pos.volume),
                        "type": int(mt5_client.ORDER_TYPE_SELL if pos.type == mt5_client.ORDER_TYPE_BUY else mt5_client.ORDER_TYPE_BUY),
                        "position": int(pos.ticket),
                        "price": float(tick.bid if pos.type == mt5_client.ORDER_TYPE_BUY else tick.ask),
                        "comment": "AI GUARDIAN CLOSE",
                        "type_filling": int(get_filling_mode(mt5_client.symbol_info(pos.symbol))),
                    }
                    mt5_client.order_send(request_audit)

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
                account_peak = float(acc_init.balance)
                global current_capital, INITIAL_CAPITAL
                # FOR SMALL CAP: Always reset to live balance on start to avoid "legacy drawdown" lock
                INITIAL_CAPITAL = account_peak
                current_capital = account_peak
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
            # Globals for components
            global market_guardian, orchestrator, meta_selector, guardian, GLOBAL_RESUME_TIME, STRATEGY_HUB_ENABLED, STRATEGY_HUB
            logger.debug("--- [STEP 0] Loop Start ---")

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
                
            equity = acc.equity
            balance = acc.balance
            daily_pnl = equity - INITIAL_CAPITAL
            is_small_cap = balance < 100
            
            # Check for AI Retraining
            check_auto_retrain()

            # --- [UNIVERSAL GUARDIAN v4.1: SYSTEM PROTECTION] ---
            if not guardian:
                guardian = UniversalGuardian(INITIAL_CAPITAL, logger)
            
            guardian.update(equity)

            # --- [V3.7 KAIZEN LOCK: ATOMIC PURGE] ---
            profit_floor = guardian.get_profit_lock_floor(equity)
            if profit_floor and equity < profit_floor:
                logger.warning(f"🚨 [KAIZEN LOCK] Equity (${equity:,.2f}) hit dynamic floor (${profit_floor:,.2f}). Saving Profits!")
                bot.send_message(f"🚨 *TRINQUETE DE BENEFICIO*: El Equity ha tocado el piso de protección. Cerrando todo para asegurar ganancias.")
                
                # PROTOCOLO V3.7: PURGA ATÓMICA
                mt5_manager.close_all_positions_atomic()
                
                # ASYNCHRONOUS COOLDOWN: 4 Horas
                GLOBAL_RESUME_TIME = time.time() + 14400 
                logger.warning(f"⏳ [COOLDOWN] System Halted. Resuming at {datetime.fromtimestamp(GLOBAL_RESUME_TIME).strftime('%H:%M:%S')}")
                continue

                
            # --- PHASE 26: TELEGRAM PULSE (Heartbeat) ---
            # PRIORITIZED: Move pulse to the very top to give user feedback immediately.
            if time.time() - last_pulse_time > 1800: # Every 60 seconds
                last_pulse_time = time.time()
                try:
                    if MT5_CONNECTED:
                        positions = mt5_client.positions_get()
                        
                        pos_summary = ""
                        block_pnl = {"ALFA": 0.0, "EXPL": 0.0, "NEME": 0.0, "WINNER": 0.0, "OTHER": 0.0}
                        if positions:
                            for p in positions:
                                swap = getattr(p, 'swap', 0.0)
                                comm = getattr(p, 'commission', 0.0)
                                profit = p.profit + swap + comm
                                comment = getattr(p, 'comment', "")
                                
                                if "ALFA" in comment: block_pnl["ALFA"] += profit
                                elif "EXPL" in comment: block_pnl["EXPL"] += profit
                                elif "NEME" in comment: block_pnl["NEME"] += profit
                                elif "WINNER" in comment: block_pnl["WINNER"] += profit
                                else: block_pnl["OTHER"] += profit
                                
                                if abs(profit) > 10.0:
                                    pos_summary += f"\n🔹 {p.symbol} {profit:+.2f}"
                            
                            block_text = (
                                f"\n🧬 *L-H-N BETA DISTRICTS*"
                                f"\n🟢 ALFA: ${block_pnl['ALFA']:+.2f}"
                                f"\n🔍 EXPL: ${block_pnl['EXPL']:+.2f}"
                                f"\n💀 NEME: ${block_pnl['NEME']:+.2f}"
                                f"\n🏆 WINNER: ${block_pnl['WINNER']:+.2f}"
                            )
                            pos_summary = block_text + pos_summary
                        else:
                            pos_summary = "\n💤 No Active Trades"
                            
                        regime_line = ""
                        if orchestrator:
                            regime_line = f"\n🎼 Régimen: {orchestrator.current_regime}"
                            
                        msg = (
                            f"💓 *STATUS PULSE* 💓\n"
                            f"💰 Bal: ${balance:,.2f}\n"
                            f"📈 Eq:  ${equity:,.2f}\n"
                            f"📊 PnL Session: ${daily_pnl:+.2f}\n"
                            f"{regime_line}"
                            f"{pos_summary}"
                        )
                        
                        if bot.enabled: 
                            bot.send_message(msg)
                            logger.info("💓 Pulse Sent to Telegram")

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
                            
                            # Shadow Log (Silent)
                            with open(BASKET_LOG, "a") as f:
                                log_entry = {
                                    "time": datetime.now().isoformat(),
                                    "pnl": round(current_basket_pnl, 4),
                                    "peak": round(basket_lifetime_peak, 4),
                                    "count": len(positions),
                                    "equity": equity
                                }
                                f.write(json.dumps(log_entry) + "\n")
                                
                except Exception as e:
                    logger.error(f"Pulse/Telemetry Error: {e}")

            # --- [UNIVERSAL GUARDIAN v4.1: ACTIVE PROTECTIONS - EVERY ITERATION] ---
            # 1. Dynamic Profit Lock (Trinquete Escalonado)
            profit_floor = guardian.get_profit_lock_floor(equity)
            if profit_floor and equity < profit_floor:
                logger.warning(f"🚨 [KAIZEN LOCK] Equity (${equity:,.2f}) hit dynamic floor (${profit_floor:,.2f}). Saving Profits!")
                bot.send_message(f"🚨 *TRINQUETE DE BENEFICIO*: El Equity ha tocado el piso de protección escalonado. Cerrando todo para asegurar ganancias.")
                mt5_manager.close_all_positions()
                time.sleep(3600 * 4) # Cool-off 4h
                continue

            # 2. Hard Fuse Safety (Daily Limit)
            # EXTREME SURVIVAL: Disable Hard Fuse for accounts < $100 to give them "one last breath"
            if INITIAL_CAPITAL >= 100:
                hard_limit_pct = (guardian.daily_limit_pct * 0.75)
                hard_limit = INITIAL_CAPITAL * (1 - (hard_limit_pct / 100))
                
                if equity < hard_limit:
                    sleep_duration = 3600 * 24 
                    logger.error(f"💀 [HARD FUSE] Equity (${equity:,.2f}) hit Limit (${hard_limit:,.2f} | {hard_limit_pct}%). Safety Cool-off: 24h")
                    bot.send_message(f"💀 *HARD FUSE*: Límite diario alcanzado. Pausando por 24h.")
                    mt5_manager.close_all_positions()
                    time.sleep(sleep_duration)
                    continue
            else:
                # Still log the status for monitoring
                logger.info(f"🛡️ [AXI EXTREME] Hard Fuse bypassed for Survival Account. Equity: ${equity:,.2f}")

            # 3. Harvest Mode (Pase de Cuenta)
            # ONLY FOR FTMO CHALLENGES: Disable for survival accounts < $100
            if INITIAL_CAPITAL >= 100 and (equity >= INITIAL_CAPITAL * 1.10):
                FTMO_TARGET = INITIAL_CAPITAL * 1.10
                peak_post = max(getattr(bot, 'peak_equity_post_target', equity), equity)
                bot.peak_equity_post_target = peak_post
                extra = peak_post - FTMO_TARGET
                harvest_threshold = FTMO_TARGET + (extra * 0.50)
                if equity < harvest_threshold:
                    logger.warning(f"🚜 [HARVEST] Cosechando Pase de Cuenta en ${equity:,.2f}.")
                    bot.send_message(f"🚜 *CONTRATO CUMPLIDO*: Protegiendo el pase de cuenta. Cosechando resultados.")
                    mt5_manager.close_all_positions()
                    time.sleep(3600 * 24)
                    continue
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

            print(f"\r⏳ Scanning... {timestamp_str} UTC | AI: {'ACTIVE' if stop_hunt_model else 'OFF'}", end="")
            sys.stdout.flush() # FORCE FLUSH for tail -f
            
            # --- PHASE 18/19: DYNAMIC PROTECTIONS ---
            # 1. Daily Loss Circuit Breaker (Non-Blocking) - Filtered by Session Start
            # BUG FIX: usar medianoche UTC del día actual, no el arranque del proceso.
            # Esto evita el Circuit Breaker infinito cuando el proceso vive entre días.
            today_midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            deals = mt5_client.history_deals_get(today_midnight, datetime.now())
            
            # --- BYPASS GUARDIAN FOR MEGA GRID DEPLOYMENT ---
            daily_limit = -1000000.0 # Unlimited loss limit temporarily ignored 
            # daily_limit = -(current_capital * 0.02)
            
            # Check if breaker already active
            breaker_active = False
            if time.time() < circuit_breaker_cooldown:
                breaker_active = True
                print(f"\r⏳ [COOLDOWN] Circuit Breaker Active. Gestión de Trades habilitada. Nuevas señales: BLOQUEADAS.", end="")

            if deals:
                daily_pnl = sum([d.profit + d.commission + d.swap for d in deals])
                if daily_pnl < daily_limit and not breaker_active:
                    warn_msg = f"🛑 AI GUARDIAN: Daily Loss Limit Hit (${daily_pnl:.2f}). Signals disabled for 1 hour."
                    print(f"\n{warn_msg}")
                    try:
                        if bot.enabled: bot.send_message(warn_msg)
                    except: pass
                    circuit_breaker_cooldown = time.time() + 3600 # 1 hour
                    breaker_active = True

            # 2. Per-Symbol Loss Limit (Advanced Shield)
            symbol_pnl_map = {}
            if deals:
                for d in deals:
                    symbol_pnl_map[d.symbol] = symbol_pnl_map.get(d.symbol, 0) + (d.profit + d.commission + d.swap)

            # --- VIRTUAL UPDATE PULSE (DEPRECATED IN FAVOR OF TICKET MONITORING) ---
            # if MT5_CONNECTED:
            #     for pair_code in ASSET_MAP.keys():
            #         sym_code = ASSET_MAP.get(pair_code)
            #         tick_data = mt5_client.symbol_info_tick(sym_code)
            #         if tick_data:
            #             virtual_manager.update(sym_code, tick_data.bid, tick_data.ask)
            
            # Skip new signals if breaker active
            if breaker_active:
                time.sleep(10) # Minimal wait to allow manage_active_trades to cycle
                continue
            
            # --- PHASE 99: BASKET COOLDOWN (Anti-Carousel) ---
            global LAST_BASKET_RELEASE_TIME
            cooldown_period = 1800 # 30 minutes
            if time.time() - LAST_BASKET_RELEASE_TIME < cooldown_period:
                remaining = int(cooldown_period - (time.time() - LAST_BASKET_RELEASE_TIME))
                if remaining % 300 == 0: # Log every 5 mins
                    logger.info(f"⏳ [COOLDOWN] Basket Recently Locked. Skipping scanning for {remaining}s")
                time.sleep(5)
                continue


            # --- [ALPHA SUPREMO PIPELINE V4.1.5] ---
            # 1. Cargar Configuración de Combate (Activos + Riesgo)
            tactical_config, requested_risk = load_tactical_config()
            
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
                    
                # Inyectar Override de Rol si mode es MANUAL
                if pair_settings.get("strategy_mode") == "MANUAL":
                    forced_role = pair_settings.get("manual_nem_role")
                    if forced_role:
                        logger.warning(f"🎯 [DASHBOARD OVERRIDE] Forzando {pair} a {forced_role}")
                # --------------------------------------------

                symbol = ASSET_MAP.get(pair)
                data = get_mt5_data(symbol, bars=200)
                if data.empty or len(data) < 50: continue
                if STRATEGY_HUB_ENABLED and STRATEGY_HUB:
                    # Get signal from StrategyHub (returns SignalResult, not list)
                    hub_result = STRATEGY_HUB.get_signal(pair, data)
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
                        mega_grid_tracker.execute_signal(signal)
                        unique_symbols.add(signal.symbol)

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
