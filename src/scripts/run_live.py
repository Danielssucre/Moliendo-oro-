#!/usr/bin/env python3
"""
NANOBOT LIVE TRADING RUNNER (v2.0 Clean)
- Strategy: HIVE V5 (Trend Sniper)
- ML Modules: Gatekeeper (Shadow), StopHunt (Active), RL Trailing (Active)
- Risk: Dynamic Institutional w/ Kelly Sizing
"""
import sys
import os
import time
import logging
import pandas as pd
import numpy as np
import json
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
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("NAANOBOT_FTMO")

# --- VIRTUAL ORDER MANAGER (SHADOW GRID) ---
# --- REAL GRID MANAGER (L-H-N REAL EXPERIMENT) ---
class RealGridManager:
    """Manages 40 real trades per signal (Thesis/Antithesis) to track real-market outcomes."""
    def __init__(self, log_file="data/research/shadow_grid_results.csv"):
        self.log_file = log_file
        self.active_trades = [] # List of dicts with {ticket, symbol, config, etc.}
        self._ensure_log_exists()

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
            if res and res.retcode == 10009:
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
    def __init__(self, port=8001):
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
                # Credenciales extraídas del JSON para puentear el error -6 de autorización de Wine Native
                import json
                try:
                    with open(DEFAULT_CREDS_PATH, "r") as f:
                        config = json.load(f)
                    
                    c_login = config["mt5"]["account"]
                    c_pass = config["mt5"]["password"]
                    c_server = config["mt5"]["server"]
                except:
                    c_login = 1521200226
                    c_pass = "Y9*VlN1c$9f*I?"
                    c_server = "FTMO-Demo2"
                    
                if self.client.initialize(path='C:\\Program Files\\MetaTrader 5\\terminal64.exe', portable=True, login=c_login, password=c_pass, server=c_server):
                    # PERFORM LOGIN if creds exist
                    if self.creds:
                        acc = int(self.creds.get("account", 0))
                        pw = self.creds.get("password", "")
                        srv = self.creds.get("server", "")
                        if acc and pw and srv:
                            if self.client.login(acc, pw, srv):
                                print(f"✅ LOGIN SUCCESSFUL: #{acc} ({srv})")
                            else:
                                print(f"❌ LOGIN FAILED: {self.client.last_error()}")
                                # We continue anyway, as it might be already logged in manually
                    
                    self.connected = True
                    MT5_CONNECTED = True
                    mt5_client = self.client
                    print(f"🍏 SILICON MT5 CONNECTED: {self.client.version()}")
                    return True
                else:
                    print(f"🍎 MT5 Connection Failed (Attempt {attempt+1}/{max_retries}): {self.client.last_error()}")
            except Exception as e:
                print(f"⚠️ MT5 Connection Error (Attempt {attempt+1}/{max_retries}): {e}")
                
            time.sleep(retry_delay)
            retry_delay *= 2 # Exponential backoff
            
        print("❌ CRITICAL: Could not connect to MT5 after multiple attempts.")
        return False

    def ensure_connected(self):
        """Called within the main loop to reconnect if dropped."""
        global MT5_CONNECTED, mt5_client
        if not self.client:
            return self.connect(max_retries=1)
            
        try:
            self.client.terminal_info()
            return True
        except:
            print("⚠️ Connection lost! Reconnecting...")
            self.connected = False
            MT5_CONNECTED = False
            return self.connect(max_retries=3)

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
        
        # 4:00 PM EST (16:00) is the start of the Smart Close window
        if est_now.hour == 16:
            positions = self.mt5.positions_get()
            if not positions: return
            
            for p in positions:
                if self.is_crypto(p.symbol): continue
                
                profit = p.profit
                
                # SMART CLOSE: If in profit after 4:00 PM, close immediately to secure it.
                if profit > 0:
                    logger.info(f"🛡️ IRON SHIELD v2 (SMART): Closing {p.symbol} in profit (${profit:.2f}) before weekend.")
                    self._close_position(p)
                
                # HARD LIMIT: If it's after 4:15 PM, close regardless of P/L.
                elif est_now.minute >= 15:
                    logger.warning(f"🛡️ IRON SHIELD v2 (HARD): Forced closure of {p.symbol} (${profit:.2f}) to prevent weekend GAP.")
                    self._close_position(p)

    def _close_position(self, p):
        """Helper to execute the close order."""
        symbol = p.symbol
        ticket = p.ticket
        type_close = 1 if p.type == 0 else 0 # Close Buy with Sell, Sell with Buy
        
        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": p.volume,
            "type": type_close,
            "position": ticket,
            "price": self.mt5.symbol_info_tick(symbol).bid if type_close == 1 else self.mt5.symbol_info_tick(symbol).ask,
            "deviation": 20,
            "magic": 10009,
            "comment": "Iron Shield v2 Exit",
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self.mt5.ORDER_FILLING_IOC,
        }
        
        res = self.mt5.order_send(request)
        if res.retcode != self.mt5.TRADE_RETCODE_DONE:
            logger.error(f"❌ IRON SHIELD v2 Failure: {res.comment} ({res.retcode})")
        else:
            logger.info(f"✅ IRON SHIELD v2 Success: Closed {symbol} #{ticket}")

market_guardian = None # To be initialized after MT5 connection

risk_pips_cache = {}

def init_mt5():
    return mt5_manager.connect()

def get_initial_risk_pips(ticket, symbol, entry_p, point):
    """
    IRON SHIELD (Phase 5 Hardening):
    Scans history to find the REAL original stop-loss.
    Uses cache to avoid redundant MT5 history queries.
    """
    global risk_pips_cache
    if ticket in risk_pips_cache:
        return risk_pips_cache[ticket]

    # Check history 1 year back to be safe
    from_date = datetime.now() - timedelta(days=365)
    deals = mt5_client.history_deals_get(from_date, datetime.now(), position=ticket)
    
    if deals:
        for d in deals:
            # Entry deal (TYPE_BUY or TYPE_SELL and ENTRY_IN)
            d_entry = getattr(d, 'entry', -1)
            d_sl    = getattr(d, 'sl', 0)
            if d_entry == 0:  # 0 is ENTRY_IN in MT5
                if d_sl > 0:
                    risk_pips = abs(entry_p - d_sl) / (point + 1e-12)
                    risk_pips_cache[ticket] = risk_pips
                    # Only log once if found
                    return risk_pips
    
    # Fallback only if history is missing or no SL was set at entry
    # No logging here to avoid spamming console
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
last_retrain_date = None
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
        
        logger.info("🧠 [LHN-THREAD] Specialized models updated on disk. Synergizing with live engine...")
        # Note: In a production environment, we'd signal the main thread to reload the models.
        # For now, the next bot restart or a specific reload trigger will pick them up.
        
    except Exception as e:
        logger.error(f"❌ [LHN-THREAD] Auto-Retrain Background Task Failed: {e}")

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

def analyze_hybrid_signal(df):
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
        triggers.append((sig, strategy, row, "LHN"))

    # SYSTEM 2: LAB 2.1 (EMA 8/16)
    if cross_8_16 != 0:
        triggers.append((cross_8_16, "LAB_E8_E16", row, "E8E16"))

    # SYSTEM 3: LAB 2.1 (EMA 12/26)
    if cross_12_26 != 0:
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


def execute_mt5_trade(pair, order_type_str, price, sl, tp, volume, comment="Nanobot HIVE V5"):
    """
    Phase 71: Execute Pending Order on Silicon MT5
    """
    if not MT5_CONNECTED: return
    
    symbol_mt5 = MT5_SYMBOL_MAP.get(pair, pair) # Fallback to pair if not in map
    
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
        "action": action,
        "symbol": symbol_mt5,
        "volume": float(volume),
        "price": float(price),
        "sl": float(sl),
        "tp": float(tp),
        "type": type_mt5,
        "type_time": mt5_client.ORDER_TIME_DAY, 
        "type_filling": filling_mode,
        "comment": comment,
    }
    
    try:
        result = mt5_client.order_send(request)
        if result.retcode != mt5_client.TRADE_RETCODE_DONE:
            err_msg = f"❌ ORDER FAILED: {result.comment} ({result.retcode})"
            logger.error(err_msg)
            if bot.enabled: bot.send_message(err_msg)
        else:
            success_msg = f"✅ ORDER PLACED: {pair} #{result.order} | Price: {result.price:.5f}"
            logger.info(success_msg)
            if bot.enabled: bot.send_message(success_msg)
        return result
    except Exception as e:
        logger.error(f"⚠️ Execution Exception: {e}")
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
    """
    Prevent over-exposure to USD and avoid duplicate symbol trades.
    """
    if not MT5_CONNECTED: return True 
    
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
    global last_trade_audit
    if not MT5_CONNECTED: return
    
    positions = mt5_client.positions_get()
    if not positions: return
    
    current_time = time.time()
    active_summary = []
    
    for p in positions:
        symbol = p.symbol
        # Type 0=Buy, 1=Sell
        
        # Get Symbol Context (ATR/Digits)
        info = mt5_client.symbol_info(symbol)
        if not info: continue
        
        # Get last ATR (Native MT5)
        rates = mt5_client.copy_rates_from_pos(symbol, 16385, 0, 20) # H1
        if rates is not None and len(rates) > 14:
            df = pd.DataFrame(rates)
            df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
            tr = pd.concat([df['high']-df['low'], abs(df['high']-df['close'].shift(1)), abs(df['low']-df['close'].shift(1))], axis=1).max(axis=1)
            df['atr'] = tr.rolling(14).mean()
            atr = df['atr'].iloc[-1]
        else:
            atr = 0.002 # Fallback
            
        # 🎯 DANIEL'S PARTIAL EXIT (1.3R): 50% Close + Move to BE
        # Phase 4 Logic Hardening: Stable R-Multiples
        entry_p = p.price_open
        tp_p = p.tp
        
        # Calculate Initial Risk (Iron Shield: Query History)
        initial_risk_pips = get_initial_risk_pips(p.ticket, symbol, entry_p, info.point)
        
        if not initial_risk_pips:
            # Fallback for manual trades or missing history: Estimate from TP
            tp_dist_pips = abs(tp_p - entry_p) / info.point if tp_p > 0 else (p.price_current * 0.003 / info.point)
            initial_risk_pips = tp_dist_pips / 1.5
            
        if initial_risk_pips < 1.0: initial_risk_pips = 10.0 # Fallback
        
        current_pips = (p.price_current - entry_p) / info.point
        r_multiple = current_pips / initial_risk_pips if p.type == 0 else (-current_pips / initial_risk_pips)
        
        # --- CORRECCIÓN #2: TIEMPO MÁXIMO DE TRADE (Armonía 2026) ---
        # 72h para Forex. 96h para BTCUSD (mercado 24/7 y ciclos distintos).
        MAX_TRADE_HOURS = 96.0 if symbol == "BTCUSD" else 72.0
        MIN_R_TO_SKIP_BE = 0.5  # Si ya ganó más de esto, no forzamos BE
        duration_hours = (datetime.now() - datetime.fromtimestamp(p.time)).total_seconds() / 3600

        if duration_hours > MAX_TRADE_HOURS and r_multiple < MIN_R_TO_SKIP_BE:
            # Calcular si el SL ya está en BE o mejor (no volver a moverlo)
            be_offset_points = max(10, info.trade_stops_level + 5)
            be_price = entry_p + (be_offset_points * info.point) if p.type == 0 else entry_p - (be_offset_points * info.point)
            sl_already_at_be = (p.type == 0 and p.sl >= be_price) or (p.type == 1 and p.sl <= be_price and p.sl > 0)

            if not sl_already_at_be:
                logger.warning(f"⏰ TIEMPO MAX ({duration_hours:.1f}h): {symbol} #{p.ticket} no ha llegado a 0.5R ({r_multiple:.2f}R). Moviendo SL a Break-Even.")
                sl_request = {
                    "action": mt5_client.TRADE_ACTION_SLTP,
                    "symbol": symbol,
                    "sl": float(be_price),
                    "tp": float(p.tp),
                    "position": p.ticket
                }
                result = mt5_client.order_send(sl_request)
                if result and result.retcode == mt5_client.TRADE_RETCODE_DONE:
                    logger.info(f"✅ TIEMPO MAX: SL de {symbol} movido a BE ({be_price:.5f}).")
                    try:
                        if bot.enabled:
                            bot.send_message(
                                f"⏰ *TIEMPO MAX ACTIVO*\n"
                                f"Par: `{symbol}` | Ticket: `#{p.ticket}`\n"
                                f"Duración: {duration_hours:.1f}h | R actual: {r_multiple:.2f}R\n"
                                f"Acción: _SL movido a Break-Even ({be_price:.5f})_"
                            )
                    except: pass
                else:
                    logger.error(f"❌ TIEMPO MAX: No se pudo mover SL de {symbol}. Código: {result.retcode if result else 'None'}")

        # Check if already partialled (Phase 3 Fix: Include MFE Sniper tag)
        is_partialed = "PARTIAL" in p.comment or "MFE" in p.comment or "SNIPER" in p.comment
        if hasattr(p, 'volume_initial') and p.volume < p.volume_initial:
            is_partialed = True

        # 🎯 MFE SNIPER (Surgical Phase): Manage partials before 1.3R
        if SNIPER_ENABLED and sniper_manager and not is_partialed:
            # Use current H1 dataframe built for ATR, pass mt5_client for MFE scanning
            action = sniper_manager.process_position(p, info, df, mt5_client=mt5_client)
            
            # Baseline compatibility: Also trigger if 1.3R reached (Safety net)
            # LHN OPTIMIZADO: Trail activa a 1.5R (backtest muestra que 1.3R era prematuro)
            if action == "PARTIAL" or r_multiple >= 1.5:
                reason = "AI SNIPER" if action == "PARTIAL" else "SAFETY 1.3R"
                print(f"🎯 PARTIAL EXIT TRIGGERED ({reason}): Closing 50% of {symbol} (#{p.ticket}).")
                partial_vol = p.volume / 2.0
                
                # Volume Hardening
                if info.volume_step > 0:
                    partial_vol = round(partial_vol / info.volume_step) * info.volume_step
                if partial_vol < info.volume_min: partial_vol = p.volume # Full close if below min
                partial_vol = round(partial_vol, 2)
                
                # Close 50%
                tick = mt5_client.symbol_info_tick(symbol)
                close_request = {
                    "action": mt5_client.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": float(partial_vol),
                    "type": mt5_client.ORDER_TYPE_SELL if p.type == 0 else mt5_client.ORDER_TYPE_BUY,
                    "position": p.ticket,
                    "price": tick.bid if p.type == 0 else tick.ask,
                    "comment": f"MFE SNIPER {reason}",
                    "type_filling": get_filling_mode(info),
                }
                mt5_client.order_send(close_request)
                
                # Move to BE (Dynamic Offset Hardening)
                be_offset_points = max(10, info.trade_stops_level + 5)
                new_sl = entry_p + (be_offset_points * info.point) if p.type == 0 else entry_p - (be_offset_points * info.point)
                sl_request = {
                    "action": mt5_client.TRADE_ACTION_SLTP,
                    "symbol": symbol,
                    "sl": float(new_sl),
                    "tp": float(p.tp),
                    "position": p.ticket
                }
                mt5_client.order_send(sl_request)
                
                try:
                    if bot.enabled:
                        bot.send_message(f"🎯 *PARTIAL EXIT ({reason})*\nPair: `{symbol}`\nTicket: `#{p.ticket}`\nAction: _Closed 50% + SL moved to BE_")
                except: pass
        
            # Gather data for AI Audit
            active_summary.append({
                'ticket': int(p.ticket),
                'symbol': symbol,
                'type': int(p.type),
                'profit_pips': float(p.profit),
                'duration_hours': (datetime.now() - datetime.fromtimestamp(p.time)).total_seconds() / 3600
            })
            
        # RL INFINITE RUNNER (Phase 72)
        if RL_AGENT_ENABLED and rl_manager and is_partialed:
            # We already have info and df (via get_mt5_data call might be needed if manage_active_trades doesn't have it)
            # Actually manage_active_trades has current H1 data in 'df' (calculated for ATR)
            if 'df' in locals() and not df.empty:
                action = rl_manager.process_position(p, info, df, mt5_client=mt5_client)
                if action == "MOVE":
                    # Move SL by 0.5R (Phase 5 NameError Fix: use initial_risk_pips)
                    # LHN OPTIMIZADO: SL move de 0.3R (trail más largo, menos cortes prematuros)
                    new_sl = p.sl + (initial_risk_pips * 0.3 * info.point) if p.type == 0 else p.sl - (initial_risk_pips * 0.3 * info.point)
                    sl_request = {
                        "action": mt5_client.TRADE_ACTION_SLTP,
                        "symbol": symbol,
                        "sl": float(new_sl),
                        "tp": float(p.tp),
                        "position": p.ticket
                    }
                    mt5_client.order_send(sl_request)
                    logger.info(f"🤖 RL AGENT: Moving SL for {symbol} (+0.5R)")
                elif action == "CLOSE":
                    print(f"💥 RL AGENT: Closing {symbol} (#{p.ticket}) for dynamic profit capture.")
                    tick = mt5_client.symbol_info_tick(symbol)
                    close_request = {
                        "action": mt5_client.TRADE_ACTION_DEAL,
                        "symbol": symbol,
                        "volume": p.volume,
                        "type": mt5_client.ORDER_TYPE_SELL if p.type == 0 else mt5_client.ORDER_TYPE_BUY,
                        "position": p.ticket,
                        "price": tick.bid if p.type == 0 else tick.ask,
                        "comment": "RL AGENT CLOSE",
                        "type_filling": get_filling_mode(info),
                    }
                    mt5_client.order_send(close_request)
                    try:
                        if bot.enabled:
                            bot.send_message(f"🤖 *RL AGENT CLOSE*\nPair: `{symbol}`\nAction: _Dynamic Close for profit capture_")
                    except: pass

    # 🧠 AI Audit (Every 30 minutes)
    # 🧠 AI Audit (Every 30 minutes)
    if bot_brain and (current_time - last_trade_audit > 1800):
        last_trade_audit = current_time
        print("🧠 AI GUARDIAN: Auditing active positions...")
        recommendations = bot_brain.audit_trade_health(active_summary)
        for rec in recommendations:
            ticket = int(rec.get('ticket', 0))
            action = rec.get('action')
            reason = rec.get('reason')
            
            if action == "CLOSE" and ticket > 0:
                print(f"💥 AI PRECAUTIONARY CLOSE: Ticket {ticket} | Reason: {reason}")
                # Find the position
                pos = next((p for p in positions if p.ticket == ticket), None)
                if pos:
                    tick = mt5_client.symbol_info_tick(pos.symbol)
                    request = {
                        "action": mt5_client.TRADE_ACTION_DEAL,
                        "symbol": pos.symbol,
                        "volume": pos.volume,
                        "type": mt5_client.ORDER_TYPE_SELL if pos.type == mt5_client.ORDER_TYPE_BUY else mt5_client.ORDER_TYPE_BUY,
                        "position": pos.ticket,
                        "price": tick.bid if pos.type == mt5_client.ORDER_TYPE_BUY else tick.ask,
                        "deviation": 20,
                        "magic": pos.magic,
                        "comment": "AI GUARDIAN CLOSE",
                        "type_time": mt5_client.ORDER_TIME_GTC,
                        "type_filling": mt5_client.ORDER_FILLING_IOC,
                    }
                    mt5_client.order_send(request)
                    try:
                        if bot.enabled:
                            bot.send_message(f"🚨 *AI GUARDIAN CLOSE*\nTicket: `{ticket}`\nReason: _{reason}_")
                    except: pass

def main():
    global current_capital, AI_RISK_FACTOR, last_trade_audit, last_risk_audit, circuit_breaker_cooldown, GATEKEEPER_MODE
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
    init_mt5()

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
                INITIAL_CAPITAL = account_peak
                current_capital = account_peak
                print(f"🏦 QUANTUM RISK RL: Active | Peak: ${account_peak:.2f}")

    # 4. Report Orders
    if MT5_CONNECTED: cleanup_pending_orders()   

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
        bot.send_message("🦖 *HIVE V5 ALL-STARS LIVE* 🟢\nSuper-Swarm Active (26 Assets)\nScanning for SMC & Fractal Setups...")
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
    
    logger.info("⚡ Entering 24/7 Signal Scan Loop...")
    
    # Track sent signals to enforce DAILY RE-ENTRY
    # {pair: 'YYYY-MM-DD'}
    last_signal_date = {} 
    
    last_pulse_time = time.time()
    
    print(f"⏳ Scanning... (Ctrl+C to stop)")
    
    while True:
        try:
            # 0. Connection Watchdog
            if not mt5_manager.ensure_connected():
                logger.error("❌ Link Lost. Waiting for recovery...")
                time.sleep(5)
                continue
            
            # --- PHASE 75: IRON SHIELD v2 (Active Guardian) ---
            global market_guardian
            if market_guardian is None and MT5_CONNECTED:
                market_guardian = MarketGuardian(mt5_client)
                logger.info("🛡️ IRON SHIELD v2: Market Guardian Initialized and Active.")
            
            if market_guardian:
                market_guardian.check_and_protect()

            # --- PHASE 76: ALL-WEATHER ORCHESTRATOR ---
            global orchestrator, meta_selector
            if orchestrator is None and MT5_CONNECTED and ORCHESTRATOR_ENABLED:
                orchestrator = BotOrchestrator(mt5_client=mt5_client)
                logger.info("🎼 ALL-WEATHER: Orchestrator Online. Regime detection active.")

            if meta_selector is None and META_SELECTOR_ENABLED:
                meta_selector = MetaRLSelector()
                logger.info("🧠 META-RL SELECTOR: Online. 3-Strategy experiment ready.")

            # Check for AI Retraining
            check_auto_retrain()

            # --- PHASE 26: TELEGRAM PULSE (Heartbeat) ---
            if time.time() - last_pulse_time > 60: # Every 60 seconds
                last_pulse_time = time.time()
                try:
                    if MT5_CONNECTED:
                        acc = mt5_client.account_info()
                        positions = mt5_client.positions_get()
                        
                        if acc:
                            equity = acc.equity
                            balance = acc.balance
                            daily_pnl = equity - INITIAL_CAPITAL # Approx daily PnL relative to start of script
                            
                            # Validar si hay cambios reales para no spamear si todo está igual
                            # Pero usuario pidió "cada minuto" explícitamente.
                            
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
                                    
                                    # Still show individual trades if significant
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
                except Exception as e:
                    logger.error(f"Pulse Error: {e}")

            # --- PHASE 15: AI TRADE GUARDIAN ---
            try:
                manage_active_trades(bot_brain)
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
            
            for pair in ASSET_MAP.keys():
                current_hour_tag = datetime.now().strftime("%Y-%m-%d %H")
                symbol = ASSET_MAP.get(pair) # Now internal map is MT5 compatible
                try:
                    # 🍏 NATIVE FTMO DATA
                    data = get_mt5_data(symbol, bars=200)
                    
                    if data.empty: continue
                    # data.columns = data.columns.str.lower() # Already lowered in helper
                    if len(data) < 50: continue
                    
                    triggers = analyze_hybrid_signal(data)
                    
                    for sig, strategy, row, source_tag in triggers:
                        if sig != 0:
                            # --- HOURLY RE-ENTRY CHECK (Per Source for Lab Collection) ---
                            signal_key = f"{pair}_{source_tag}"
                            last_hour_tag = last_signal_date.get(signal_key)
                            
                            if last_hour_tag == current_hour_tag:
                                # We already processed this pair this hour.
                                continue

                            # 0. Per-Symbol Hard Stop Check
                            sym_pnl = symbol_pnl_map.get(symbol, 0)
                            sym_limit = -(current_capital * 0.01) # 1% limit per symbol
                            if sym_pnl < sym_limit:
                                logger.warning(f"🚫 [SOFT BLOCKED] {pair} hit symbol loss limit (${sym_pnl:.2f} < ${sym_limit:.2f})")
                                continue
                                
                            logger.info(f"🔍 [1/5] SIGNAL: {pair} | {'BUY' if sig==1 else 'SELL'} | Str: {strategy} | Src: {source_tag}")
                            # 1. Broad Market Filter (Relaxed for Mega Grid)
                            adx_val = row['adx']
                            try:
                                returns = data['close'].pct_change()
                                current_vol = (returns.rolling(24).std() * 1000).iloc[-1]
                            except: current_vol = 20.0

                            # Adjusted global filter to allow FRACTAL Probing (ADX > 10). 
                            # LHN EXPERIMENTO MASIVO: ADX>10 para dejar pasar todas las sub-configs
                            if not (adx_val > 20 and current_vol < 100):
                                logger.info(f"🚫 [2/5] HIVE REJECTED: {pair} (ADX={adx_val:.1f} <20 o Vol={current_vol:.1f} >=100)")
                                continue
                            
                            logger.info(f"✅ [2/5] HIVE PASSED: {pair} (ADX={adx_val:.1f}, Vol={current_vol:.1f})")
                            if bot.enabled:
                                bot.send_message(f"📡 *Signal Detected:* `{pair}` ({source_tag}) | ADX: {adx_val:.1f}\nProcessing Laboratorio L-H-N...")

                            # 2. Market Regime & ML Check
                            prev = data.iloc[-2] if len(data) > 1 else row
                            adx_slope = row['adx'] - prev['adx']
                            regime = "TRENDING" if (adx_val > 20 and adx_slope > 0) else "RANGING"
                            logger.info(f"📊 [3/6] MARKET REGIME: {pair} is {regime} (ADX={adx_val:.1f}, Slope={adx_slope:.2f})")
                            
                            ml_risk_score = 0.5 # Default
                            prob_success = 0.5 # Default
                            confidence_factor = 1.0
                            
                            # --- PHASE 23: QUANTUM RISK ORACLE (Asymmetric Sizing) ---
                            bayesian_mult = 1.0
                            if RISK_ORACLE_ENABLED and risk_oracle:
                                if ML_ENABLED and stop_hunt_model:
                                    try:
                                        features = stop_hunt_model.extract_features(data, row['close'], {'rsi': row['rsi'], 'adx': row['adx'], 'atr': row['atr'], 'vwap': row['close']})
                                        ml_risk_score = stop_hunt_model.predict_risk(features)
                                        prob_success = 1.0 - ml_risk_score
                                        
                                        # Calculate Portfolio Heat (Total current risk)
                                        exposure_heat = 0.0
                                        if MT5_CONNECTED:
                                            from src.nanobot.ml.risk_oracle import calculate_portfolio_heat
                                            exposure_heat = calculate_portfolio_heat(mt5_client, None)
                                            acc = mt5_client.account_info()
                                            if acc:
                                                account_peak = max(account_peak, float(acc.balance))
                                                current_dd = (account_peak - float(acc.balance)) / account_peak
                                            else: current_dd = 0.0
                                        else: current_dd = 0.0
                                        
                                        # Quantum RL/Math Sizing!
                                        bayesian_mult = risk_oracle.calculate_sizing_multiplier(
                                            probability=prob_success, 
                                            reward_risk=1.5, 
                                            current_dd=current_dd,
                                            exposure_heat=exposure_heat,
                                            adx=adx_val,
                                            rsi=row['rsi'],
                                            vol=current_vol,
                                            symbol=pair
                                        )
                                        
                                        # --- MEGA GRID SNIPER PROBABILITY FILTER (> 75%) ---
                                        is_sniper_valid = True
                                        if prob_success < 0.75:
                                            logger.info(f"⚖️ [SNIPER] {pair} Prob={prob_success:.2%} (Needs > 75%) -> Data Grid Only")
                                            is_sniper_valid = False
                                        
                                        if bayesian_mult <= 0:
                                            logger.info(f"⚖️ [ORACLE SKIP] {pair} Neutral edge -> Data Grid Only")
                                            is_sniper_valid = False

                                    except Exception as e:
                                        logger.error(f"⚠️ ML/Oracle Error: {e}")
                                        is_sniper_valid = False

                            # --- 4. EXECUTION ---
                            if MT5_CONNECTED:
                                logger.info(f"🦖 [EXECUTION / DATA COLLECTION] {pair} @ {row['close']:.4f}")
                                entry_price = row['close']
                                
                                # --- MARKET STATUS CHECK ---
                                symbol_info = mt5_client.symbol_info(pair)
                                if symbol_info is None or not symbol_info.visible:
                                    logger.warning(f"⚠️ {pair} NOT visible/valid on MT5. Skipping.")
                                    continue
                                
                                if symbol_info.trade_mode == mt5_client.SYMBOL_TRADE_MODE_DISABLED:
                                    logger.warning(f"⚠️ {pair} Trade DISABLED. Skipping.")
                                    last_signal_date[pair] = current_hour_tag # Don't loop
                                    continue

                                # --- TIME FENCING & CHAMELEON LOGIC (Based on Data Sciencer Insight) ---
                                tick = mt5_client.symbol_info_tick(pair)
                                if tick:
                                    current_mt5_hour = datetime.fromtimestamp(tick.time).hour
                                else:
                                    current_mt5_hour = datetime.now().hour # Fallback
                                    
                                if POLIMATA_ENABLED and polimata_model is not None:
                                    # Define known symbols from training
                                    known_symbols = ['AUDJPY', 'BTCUSD', 'CADJPY', 'ETHUSD', 'EURAUD', 'EURGBP', 'EURNZD', 'GBPAUD', 'GBPUSD', 'NZDJPY', 'SOLUSD', 'USDCAD']
                                    sym_idx = known_symbols.index(pair) if pair in known_symbols else 0
                                        
                                    obs = np.array([current_mt5_hour, sym_idx], dtype=np.float32)
                                    action, _ = polimata_model.predict(obs, deterministic=True)
                                    
                                    # Actions: 0=Skip, 1=ALFA, 2=EXPL, 3=NEME
                                    if action == 0:
                                        is_sniper_valid = False
                                        sniper_mode_name = "POLIMATA_SKIP"
                                        actual_sig = sig
                                        rr = 1.0
                                        logger.info(f"🧠 [POLIMATA] Predicted SKIP for {pair} at {current_mt5_hour}:00")
                                    elif action == 1:
                                        actual_sig = sig
                                        rr = 1.5
                                        sniper_mode_name = "LHN_ALFA_POLIMATA_H1"
                                    elif action == 2:
                                        actual_sig = sig
                                        rr = 2.5
                                        sniper_mode_name = "LHN_EXPL_POLIMATA_H1"
                                    elif action == 3:
                                        actual_sig = -sig
                                        rr = 1.5
                                        sniper_mode_name = "LHN_NEME_POLIMATA_H1"
                                else:
                                    # 1. Fase Nocturna / Asiática (00:00 a 08:59 y 20:00+): NEMESIS
                                    if (0 <= current_mt5_hour <= 8) or current_mt5_hour >= 20:
                                        actual_sig = -sig # NEMESIS (Market in Range, fake breakouts)
                                        rr = 1.5
                                        sniper_mode_name = "LHN_NEMESIS_SNIPER_H1"
                                    # 2. Fase de Caza Inicios de Londres/Europa (09:00 - 09:59): ALFA
                                    elif current_mt5_hour == 9 or current_mt5_hour == 10:
                                        # Data Analytics showed ALFA dominates at 9:00. Let's include 9-10 in ALFA mode.
                                        actual_sig = sig # ALFA (Real Breakout)
                                        rr = 1.5
                                        sniper_mode_name = "LHN_ALFA_SNIPER_H1"
                                    # 3. Fase de Silencio (NY Session & Choppy Time): OFF
                                    else:
                                        actual_sig = sig
                                        rr = 1.5
                                        sniper_mode_name = "LHN_OFFLINE"
                                        is_sniper_valid = False # 🛑 Bloqueo total
                                        logger.info(f"🛑 [TIME FENCING] Sniper OFF during Choppy Hours ({current_mt5_hour}:00). Grid Only.")
                                    
                                sl_dist = float(row['atr']) * 1.5
                                tp_dist = sl_dist * rr # Hardcoded to 1.5 RR
                                
                                c_sl = float(entry_price) - sl_dist if actual_sig == 1 else float(entry_price) + sl_dist
                                c_tp = float(entry_price) + tp_dist if actual_sig == 1 else float(entry_price) - tp_dist
                                c_order_type = "BS (Buy Stop)" if actual_sig == 1 else "SS (Sell Stop)"
                                
                                # --- DUAL SNIPER EXECUTION (Polimata vs Chameleon Benchmark) ---
                                acc_info = mt5_client.account_info()
                                if acc_info:
                                    risk_usd = float(acc_info.balance) * 0.005 # Updated to 0.5% risk
                                    tick_size = symbol_info.trade_tick_size
                                    tick_value = symbol_info.trade_tick_value
                                    if tick_size > 0 and tick_value > 0:
                                        loss_per_lot = (sl_dist / tick_size) * tick_value
                                        lots_calculated = risk_usd / loss_per_lot if loss_per_lot > 0 else 0.01
                                    else:
                                        lots_calculated = 0.02 # fallback
                                else:
                                    lots_calculated = 0.02

                                # 1. Execute Polimata Sniper (Primary)
                                if is_sniper_valid:
                                    res_p = execute_mt5_trade(pair, c_order_type, float(entry_price), c_sl, c_tp, lots_calculated, comment=sniper_mode_name)
                                    if res_p and res_p.retcode != 10018:
                                        if bot.enabled:
                                            bot.send_message(f"🧠 *{sniper_mode_name} ACTIVATED*\nPair: `{pair}`\nRisk: 0.5% | Prob: {prob_success:.2%}")

                                # 2. Execute Chameleon Sniper (Benchmark)
                                # Re-calculate Chameleon Logic for real execution
                                if (0 <= current_mt5_hour <= 8) or current_mt5_hour >= 20:
                                    cham_sig = -sig
                                    cham_mode = "CHAM_NEME_LIVE"
                                elif 9 <= current_mt5_hour <= 10:
                                    cham_sig = sig
                                    cham_mode = "CHAM_ALFA_LIVE"
                                else:
                                    cham_sig = sig
                                    cham_mode = "CHAM_OFFLINE"

                                # Chameleon is always "valid" for benchmark purposes unless in offline mode if you wish
                                is_cham_valid = True if "OFFLINE" not in cham_mode else False
                                
                                if is_cham_valid:
                                    cham_sl = float(entry_price) - sl_dist if cham_sig == 1 else float(entry_price) + sl_dist
                                    cham_tp = float(entry_price) + tp_dist if cham_sig == 1 else float(entry_price) - tp_dist
                                    cham_order = "BS (Buy Stop)" if cham_sig == 1 else "SS (Sell Stop)"
                                    
                                    res_c = execute_mt5_trade(pair, cham_order, float(entry_price), cham_sl, cham_tp, lots_calculated, comment=cham_mode)
                                    if res_c and res_c.retcode != 10018:
                                        if bot.enabled:
                                            bot.send_message(f"🦎 *{cham_mode} BENCHMARK*\nPair: `{pair}`\nRisk: 0.5% | Mode: Session Logic")

                                # --- 3. Execute Chameleon 2.0 (Cluster Punch Evolution) ---
                                cham2_sig, cham2_mode = None, "CHAM2_OFF"
                                # NÉMESIS es el Héroe en Criptos & Pares Killer
                                if pair in ['BTCUSD', 'ETHUSD', 'SOLUSD']: # Adding SOL as well
                                    cham2_sig, cham2_mode = -sig, "CHAM2_NEME_CRYPTO"
                                elif pair in ['EURAUD', 'GBPAUD', 'AUDJPY', 'NZDJPY']:
                                    cham2_sig, cham2_mode = -sig, "CHAM2_NEME_KILLER"
                                # El Dominio de ALFA en tendencias limpias
                                elif pair in ['EURNZD', 'USDCAD']:
                                    cham2_sig, cham2_mode = sig, "CHAM2_ALFA_TREND"
                                # Zona de Alerta (Quincena/Quarantine)
                                elif pair == 'GBPUSD':
                                    cham2_sig, cham2_mode = None, "CHAM2_SKIP_QUARANTINE"
                                    logger.info(f"🛡️ [CHAM2] Quarantining {pair} due to low expectancy cluster.")

                                if cham2_sig is not None:
                                    # Fixed 1.5R target for Chameleon 2.0 (The Sweet Spot)
                                    c2_rr = 1.5
                                    c2_sl_dist = float(row['atr']) * 1.5
                                    c2_tp_dist = c2_sl_dist * c2_rr
                                    
                                    c2_sl = float(entry_price) - c2_sl_dist if cham2_sig == 1 else float(entry_price) + c2_sl_dist
                                    c2_tp = float(entry_price) + c2_tp_dist if cham2_sig == 1 else float(entry_price) - c2_tp_dist
                                    c2_order = "BS (Buy Stop)" if cham2_sig == 1 else "SS (Sell Stop)"
                                    
                                    res_c2 = execute_mt5_trade(pair, c2_order, float(entry_price), c2_sl, c2_tp, lots_calculated, comment=cham2_mode)
                                    if res_c2 and res_c2.retcode != 10018:
                                        if bot.enabled:
                                            bot.send_message(f"🧬 *{cham2_mode} EVOLUTION*\nPair: `{pair}`\nRisk: 0.5% | Mode: Cluster Expert")

                                # --- 4. Execute ALFA NEMESIS (The Data-Driven Hybrid) ---
                                hybrid_sig, hybrid_mode = None, "ALFA_NEME_OFF"
                                weekday = datetime.now().weekday() # 0=Mon, 1=Tue...
                                
                                # Filters based on the survival audit
                                alfa_habitats = ['EURUSD', 'EURNZD', 'USDJPY', 'USDCAD']
                                alfa_gold_hours = [9, 11, 12] 
                                is_alfa_safe_day = (weekday != 1) # NOT Tuesday (Martes)
                                
                                if pair in alfa_habitats and current_mt5_hour in alfa_gold_hours and is_alfa_safe_day:
                                    hybrid_sig = sig # Go with the Trend (ALFA)
                                    hybrid_mode = "HYBRID_ALFA_GOLD"
                                else:
                                    hybrid_sig = -sig # Go Against (NEMESIS)
                                    hybrid_mode = "HYBRID_NEME_SHIELD"
                                
                                # Execution for ALFA NEMESIS Hybrid (0.5% Risk)
                                # h_sl_dist = float(row['atr']) * 1.5
                                # h_tp_dist = h_sl_dist * 1.5
                                h_sl = float(entry_price) - sl_dist if hybrid_sig == 1 else float(entry_price) + sl_dist
                                h_tp = float(entry_price) + tp_dist if hybrid_sig == 1 else float(entry_price) - tp_dist
                                h_order = "BS (Buy Stop)" if hybrid_sig == 1 else "SS (Sell Stop)"
                                
                                res_h = execute_mt5_trade(pair, h_order, float(entry_price), h_sl, h_tp, lots_calculated, comment=hybrid_mode)
                                if res_h and res_h.retcode != 10018:
                                    if bot.enabled:
                                        bot.send_message(f"🎭 *{hybrid_mode} HYBRID*\nPair: `{pair}`\nLogic: Hybrid Data Selection")

                                # --- MASSIVE DATA COLLECTION (MEGA GRID) ---
                                dist_ema200 = (float(entry_price) - row['ema_200']) / row['ema_200']
                                
                                virtual_manager.register_signal_pool(
                                    pair, entry_price, row['atr'], 
                                    adx_val, row['rsi'], current_vol, prob_success, sig,
                                    dist_ema200=dist_ema200,
                                    source=source_tag
                                )
                                
                                if bot.enabled and source_tag == "LHN":
                                    bot.send_message(f"📡 *MEGA GRID SENSOR (25/25/25/25)*\nPair: `{pair}` | Grid: Balanced 40 variants.")
                                elif bot.enabled:
                                    bot.send_message(f"🧪 *EXPERIMENTAL TRIGGER*\nPair: `{pair}` | Precision Lab Grid (8 variants).")
                                
                                last_signal_date[signal_key] = current_hour_tag

                except Exception as e:
                    logger.error(f"Iter Error ({pair}): {e}")
            
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
    import threading
    polimata_thread = threading.Thread(target=nightly_polimata_retrain, daemon=True)
    polimata_thread.start()
    main()
