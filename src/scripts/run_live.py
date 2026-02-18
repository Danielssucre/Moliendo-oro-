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
from datetime import datetime

# Add project root to path (Two levels up from src/scripts/)
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

from src.nanobot.ml.rl_trailing import RLTrailingManager
RL_AGENT_ENABLED = True

import argparse

# --- ARGS ---
parser = argparse.ArgumentParser(description='Nanobot Live Runner v2.0')
parser.add_argument('--capital', type=float, default=10000, help='Account Balance')
args = parser.parse_args()

# --- CONFIGURATION ---
INITIAL_CAPITAL = args.capital
current_capital = INITIAL_CAPITAL # Default fallback

# Risk Management (Updated Phase 45: "Fast FTMO")
RISK_PER_TRADE = 0.004 # 0.4% (Scientific Sweet Spot)

# --- SILICON MT5 INTEGRATION (Phase 70) 🍏 ---
# --- SILICON MT5 INTEGRATION (Phase 70) 🍏 ---
MT5_CONNECTED = False
mt5_client = None

def init_mt5():
    global MT5_CONNECTED, mt5_client
    try:
        from siliconmetatrader5 import MetaTrader5
        mt5_client = MetaTrader5(port=8001)
        if mt5_client.initialize():
            MT5_CONNECTED = True
            print(f"🍏 SILICON MT5 CONNECTED: {mt5_client.version()}")
        else:
            print(f"🍎 MT5 Connection Failed: {mt5_client.last_error()}")
    except Exception as e:
        print(f"⚠️ SiliconLib Error: {e}")


# Asset Mapping (HIVE V5 ALL-STARS)
# Top 11 Performers from "Expansion Scan" (Profit > $300)
ASSET_MAP = {
    "AUDUSD": "AUDUSD",
    "GBPJPY": "GBPJPY",
    "BTCUSD": "BTCUSD",
    "NZDUSD": "NZDUSD",
    "USDCHF": "USDCHF",
    "EURNZD": "EURNZD",
    "GBPUSD": "GBPUSD",
    "GBPNZD": "GBPNZD",
    "USDJPY": "USDJPY",
    "USDCAD": "USDCAD"
}
# Phase 71: Auto-Execution Map (Verified 1:1)
MT5_SYMBOL_MAP = {
    "AUDUSD": "AUDUSD",
    "GBPJPY": "GBPJPY",
    "BTCUSD": "BTCUSD",
    "NZDUSD": "NZDUSD",
    "USDCHF": "USDCHF",
    "EURNZD": "EURNZD",
    "GBPUSD": "GBPUSD",
    "GBPNZD": "GBPNZD",
    "USDJPY": "USDJPY",
    "USDCAD": "USDCAD"
}
MAX_SPREAD_PIPS = 4.0 # Slightly higher for crypto/crosses

PENDING_ORDER_BUFFER_PIPS = 2.0
LIMIT_ORDER_RETRACT_PIPS = 3.0

# Setup logging (Console + File)
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
if not os.path.exists(log_dir): os.makedirs(log_dir)

log_file = os.path.join(log_dir, f"trading_{datetime.now().strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger("NAANOBOT_FTMO")

# Init ML
stop_hunt_model = StopHuntModel() if ML_ENABLED else None
last_retrain_date = None
AI_RISK_FACTOR = 1.0 # Phase 14
last_trade_audit = 0 # Phase 15: Intelligent Management
last_risk_audit = 0 # Phase 16: System Synergy

# Init RL Manager
rl_manager = RLTrailingManager() if RL_AGENT_ENABLED else None

# AI GATES
GATEKEEPER_MODE = "SHADOW" # "ACTIVE" (Blocks trades) or "SHADOW" (Logs only) or "OFF"
GATEKEEPER_MODEL_PATH = "models/gatekeeper_qnet_v2.pth"
GATEKEEPER_SCALER_PATH = "models/gatekeeper_scaler_v2.json"

def check_auto_retrain():
    """Run retraining on Sundays"""
    global stop_hunt_model, last_retrain_date
    now = datetime.now()
    
    # Sunday = 6
    if now.weekday() == 6:
        today_str = now.strftime("%Y-%m-%d")
        if last_retrain_date != today_str:
            logger.info("📅 SUNDAY DETECTED: Starting Auto-Retraining Ritual...")
            try:
                # Dynamic import to avoid circular dependency issues at top level
                import subprocess
                
                # Execute training script as subprocess to ensure clean memory
                script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "train_model_60d.py")
                subprocess.run([sys.executable, script_path], check=True)
                
                # Reload Model
                if ML_ENABLED:
                    stop_hunt_model = StopHuntModel()
                    logger.info("🧠 Model Reloaded Successfully!")
                
                last_retrain_date = today_str
                
            except Exception as e:
                logger.error(f"❌ Auto-Retrain Failed: {e}")

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
    Core Logic: HIVE V5 - Trend State Check (Not Crossover)
    """
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['atr'] = calculate_atr(df)
    
    # ADX
    period = 14
    high = df['high']; low = df['low']; close = df['close']
    tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr_smooth = tr.ewm(alpha=1/period, adjust=False).mean()
    up = high.diff(); down = -low.diff()
    plus_dm = pd.Series(0.0, index=df.index); minus_dm = pd.Series(0.0, index=df.index)
    plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
    minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    df['adx'] = dx.ewm(alpha=1/period, adjust=False).mean()
    
    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(7).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(7).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Check Last Candle
    row = df.iloc[-1]
    
    sig = 0
    strategy = "None"
    
    # HIVE V5 STATE LOGIC:
    # Are we IN a Trend? (EMA9 > EMA15 > EMA200)
    # We do NOT check "prev" (Crossover). We check "Current State".
    
    # Buy State
    if row['ema_9'] > row['ema_15'] and row['close'] > row['ema_200']:
        sig = 1; strategy = "HIVE V5 Buy State"
    # Sell State
    elif row['ema_9'] < row['ema_15'] and row['close'] < row['ema_200']:
        sig = -1; strategy = "HIVE V5 Sell State"
            
    return sig, strategy, row

def execute_mt5_trade(pair, order_type_str, price, sl, tp, volume):
    """
    Phase 71: Execute Pending Order on Silicon MT5
    """
    if not MT5_CONNECTED: return
    
    symbol_mt5 = MT5_SYMBOL_MAP.get(pair)
    if not symbol_mt5:
        print(f"❌ MT5 Mapping Not Found for {pair}")
        return

    # Check Spread & Tick
    info = mt5_client.symbol_info(symbol_mt5)
    tick = mt5_client.symbol_info_tick(symbol_mt5)
    if not info or not tick:
        print(f"❌ Symbol Info/Tick Failed: {symbol_mt5}")
        return
        
    # --- SMART ENTRY (Live Data) ---
    # Convert points/pips
    pip_val = 0.01 if "JPY" in pair else 0.0001
    if "BTC" in pair: pip_val = 1.0 # Crypto points usually $1
    if "SOL" in pair: pip_val = 0.1
    
    buffer_val = PENDING_ORDER_BUFFER_PIPS * pip_val
    
    # Calculate Distances from original yfinance signal
    sl_dist = abs(price - sl)
    tp_dist = abs(price - tp)
    
    if "BS" in order_type_str:
        # Buy Stop > Ask
        new_price = tick.ask + buffer_val
        new_sl = new_price - sl_dist
        new_tp = new_price + tp_dist
    else:
        # Sell Stop < Bid
        new_price = tick.bid - buffer_val
        new_sl = new_price + sl_dist
        new_tp = new_price - tp_dist
        
    # Overwrite used vars
    price = new_price
    sl = new_sl
    tp = new_tp

    # Check Live Spread
    live_spread_pips = (tick.ask - tick.bid) / pip_val
    if live_spread_pips > MAX_SPREAD_PIPS and "USD" in pair and "BTC" not in pair:
        print(f"⚠️ SPREAD HIGH: {live_spread_pips:.1f} > {MAX_SPREAD_PIPS}")
        return

    # Check Stops Level (Minimum distance)
    stops_level = info.trade_stops_level * info.point
    min_dist = stops_level * 1.5 # Safety Factor
    
    if "BS" in order_type_str:
        if abs(price - tick.ask) < min_dist:
            print(f"⚠️ PRICE TOO CLOSE: Adjusting BS to Min Dist ({min_dist})")
            price = tick.ask + min_dist
    else:
        if abs(price - tick.bid) < min_dist:
            print(f"⚠️ PRICE TOO CLOSE: Adjusting SS to Min Dist ({min_dist})")
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
    
    print(f"🤖 EXECUTING {pair}: {volume} lots @ {price}")
    
    action = mt5_client.TRADE_ACTION_PENDING
    if "BS" in order_type_str:
        type_mt5 = mt5_client.ORDER_TYPE_BUY_STOP
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
        "type_filling": mt5_client.ORDER_FILLING_RETURN,
        "comment": "Nanobot HIVE V5",
    }
    
    try:
        result = mt5_client.order_send(request)
        if result.retcode != mt5_client.TRADE_RETCODE_DONE:
            print(f"❌ ORDER FAILED: {result.comment} ({result.retcode})")
        else:
            print(f"✅ ORDER PLACED: #{result.order} | Price: {result.price}")
    except Exception as e:
        print(f"⚠️ Execution Exception: {e}")

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
            print(f"#{o.ticket} | {o.symbol} | {o.type} | Open: {o.price_open} | Hive: {is_hive}")
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
    asset_class = "CRYPTO" if ("BTC" in new_pair or "SOL" in new_pair) else "FOREX"
    
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
        p_asset_class = "CRYPTO" if ("BTC" in symbol or "SOL" in symbol) else "FOREX"
        if p_asset_class == asset_class:
            is_buy = "BUY" in new_type or "BS" in new_type
            p_is_buy = (p_type == 0) # Simple map for demo, MT5 uses specific enums for orders
            if is_buy == p_is_buy:
                class_direction_count += 1
                
        if "USD" in symbol:
            if p_type == 0: usd_shorts += 1
            else: usd_longs += 1
             
    # 4. Apply Advanced Filters
    if class_direction_count >= 2:
        print(f"🔗 ASSET CLASS SATURATION: Already 2 trades in same direction for {asset_class}. Blocking {new_pair}.")
        return False

    # Evaluate New Trade USD Correlation
    if is_usd_pair:
        if "BUY" in new_type or "BS" in new_type: # Sell USD
            if usd_shorts >= 2:
                print(f"🔗 CORRELATION FILTER: Too many USD Shorts ({usd_shorts}). Blocking {new_pair}.")
                return False
        else: # Buy USD
            if usd_longs >= 2:
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
            # Silicon MT5 returns columns as named fields in a numpy array
            high = df['high']; low = df['low']; close = df['close']
            tr = pd.concat([high-low, abs(high-close.shift(1)), abs(low-close.shift(1))], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
        else:
            atr = 0.002 # Fallback
            
        # 🎯 DANIEL'S PARTIAL EXIT (1.3R): 50% Close + Move to BE
        # 🟢 BUY Logic
        entry_p = p.price_open
        sl_p = p.sl
        risk_pips = abs(entry_p - sl_p) / info.point if sl_p > 0 else 0
        current_pips = (p.price_current - entry_p) / info.point
        r_multiple = current_pips / (risk_pips + 0.00001) if p.type == 0 else (-current_pips / (risk_pips + 0.00001))
        
        # Check if already partialled (Using comment or local state? Using comment "PARTIAL" is safer)
        is_partialed = "PARTIAL" in p.comment or p.volume < (p.volume_initial if hasattr(p, 'volume_initial') else p.volume)

        if not is_partialed and r_multiple >= 1.3:
            print(f"🎯 PARTIAL 1.3R REACHED: Closing 50% of {symbol} (#{p.ticket}).")
            partial_vol = round(p.volume / 2.0, 2)
            if partial_vol < info.volume_min: partial_vol = p.volume # Close all if too small
            
            # Close 50%
            tick = mt5_client.symbol_info_tick(symbol)
            close_request = {
                "action": mt5_client.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(partial_vol),
                "type": mt5_client.ORDER_TYPE_SELL if p.type == 0 else mt5_client.ORDER_TYPE_BUY,
                "position": p.ticket,
                "price": tick.bid if p.type == 0 else tick.ask,
                "comment": "PARTIAL 1.3R",
                "type_filling": mt5_client.ORDER_FILLING_IOC,
            }
            mt5_client.order_send(close_request)
            
            # Move to BE
            new_sl = entry_p + (20 * info.point) if p.type == 0 else entry_p - (20 * info.point)
            sl_request = {
                "action": mt5_client.TRADE_ACTION_SLTP,
                "symbol": symbol,
                "sl": float(new_sl),
                "tp": float(p.tp),
                "position": p.ticket
            }
            mt5_client.order_send(sl_request)
            
            # --- Telegram Notification ---
            try:
                bot = TelegramBot()
                if bot.enabled:
                    bot.send_message(f"🎯 *PARTIAL EXIT HIT*\nPair: `{symbol}`\nTicket: `#{p.ticket}`\nAction: _Closed 50% @ 1.3R + SL moved to BE_")
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
                action = rl_manager.process_position(p, info, df)
                if action == "MOVE":
                    # Move SL by 0.5R
                    new_sl = p.sl + (risk_pips * 0.5 * info.point) if p.type == 0 else p.sl - (risk_pips * 0.5 * info.point)
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
                        "type_filling": mt5_client.ORDER_FILLING_IOC,
                    }
                    mt5_client.order_send(close_request)
                    try:
                        bot = TelegramBot()
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
                        bot = TelegramBot()
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

    # Initialize Bayesian and Kelly Engines
    kelly_engine = None
    account_peak = 0.0
    if BAYES_ENABLED:
        from src.nanobot.kelly_sizing import KellyBeliefEngine
        kelly_engine = KellyBeliefEngine(fraction=0.25)
        
        # Initial Balance to start peak tracking
        if MT5_CONNECTED:
            acc_init = mt5_client.account_info()
            if acc_init:
                account_peak = float(acc_init.balance)
                global current_capital
                current_capital = account_peak
                print(f"⚖️ KELLY SIZING ENGINE: Active (Fractional 0.25x) | Peak: ${account_peak:.2f} | Risk Base: ${current_capital:.2f}")

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
    
    # Telegram Startup
    try:
        bot = TelegramBot()
        if bot.enabled:
            bot.send_message("🦖 *HIVE V5 ALL-STARS LIVE* 🟢\nLoaded Top 11 Pairs.\nScanning for Daily Golden Setups...")
    except: pass
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
    
    print(f"⏳ Scanning... (Ctrl+C to stop)")
    
    while True:
        try:
            # Check for AI Retraining
            check_auto_retrain()

            # --- PHASE 15: AI TRADE GUARDIAN ---
            try:
                manage_active_trades(bot_brain)
            except Exception as e:
                logger.error(f"Guardian Error: {e}")
            
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
            deals = mt5_client.history_deals_get(session_start_time, datetime.now())
            daily_limit = -(current_capital * 0.02)
            
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
                        bot = TelegramBot()
                        if bot.enabled: bot.send_message(warn_msg)
                    except: pass
                    circuit_breaker_cooldown = time.time() + 3600 # 1 hour
                    breaker_active = True

            # 2. Per-Symbol Loss Limit (Advanced Shield)
            symbol_pnl_map = {}
            if deals:
                for d in deals:
                    symbol_pnl_map[d.symbol] = symbol_pnl_map.get(d.symbol, 0) + (d.profit + d.commission + d.swap)
            
            # Skip new signals if breaker active
            if breaker_active:
                time.sleep(10) # Minimal wait to allow manage_active_trades to cycle
                continue
            
            for pair in ASSET_MAP.keys():
                symbol = ASSET_MAP.get(pair) # Now internal map is MT5 compatible
                try:
                    # 🍏 NATIVE FTMO DATA
                    data = get_mt5_data(symbol, bars=200)
                    
                    if data.empty: continue
                    # data.columns = data.columns.str.lower() # Already lowered in helper
                    if len(data) < 50: continue
                    
                    sig, strategy, row = analyze_hybrid_signal(data)
                    
                    if sig != 0:
                        # --- DAILY RE-ENTRY CHECK ---
                        current_date = datetime.now().strftime("%Y-%m-%d")
                        last_date = last_signal_date.get(pair)
                        
                        if last_date == current_date:
                            continue

                        # 0. Per-Symbol Hard Stop Check
                        sym_pnl = symbol_pnl_map.get(symbol, 0)
                        sym_limit = -(current_capital * 0.01) # 1% limit per symbol
                        if sym_pnl < sym_limit:
                            logger.warning(f"🚫 [SOFT BLOCKED] {pair} hit symbol loss limit (${sym_pnl:.2f} < ${sym_limit:.2f})")
                            continue
                            
                        logger.info(f"🔍 [1/5] SIGNAL FOUND: {pair} ({'BUY' if sig==1 else 'SELL'})")
                        # 1. HIVE V5 Technical Filters
                        adx_val = row['adx']
                        try:
                            returns = data['close'].pct_change()
                            current_vol = (returns.rolling(24).std() * 1000).iloc[-1]
                        except: current_vol = 20.0
                        
                        # Relaxed from 20/16 to 15/18 as per analysis
                        if not (adx_val > 15 and current_vol < 18): 
                            logger.info(f"🚫 [2/5] HIVE REJECTED: {pair} (ADX={adx_val:.1f}, Vol={current_vol:.1f})")
                            continue 
                        
                        logger.info(f"✅ [2/5] HIVE PASSED: {pair} (ADX={adx_val:.1f}, Vol={current_vol:.1f})")

                        # 2. Market Regime & ML Check
                        prev = data.iloc[-2] if len(data) > 1 else row
                        adx_slope = row['adx'] - prev['adx']
                        regime = "TRENDING" if (adx_val > 20 and adx_slope > 0) else "RANGING"
                        logger.info(f"📊 [3/6] MARKET REGIME: {pair} is {regime} (ADX={adx_val:.1f}, Slope={adx_slope:.2f})")
                        
                        ml_risk_score = 0.5 # Default
                        confidence_factor = 1.0
                        
                        # --- PHASE 22: FRACTIONAL KELLY SIZING (Calibrated) ---
                        bayesian_mult = 1.0
                        if kelly_engine:
                            if ML_ENABLED and stop_hunt_model:
                                try:
                                    features = stop_hunt_model.extract_features(data, row['close'], {'rsi': row['rsi'], 'adx': row['adx'], 'atr': row['atr'], 'vwap': row['close']})
                                    ml_risk_score = stop_hunt_model.predict_risk(features)
                                    
                                    # Calibrated Success Prob = 1.0 - ML Risk (Trap Probability)
                                    prob_success = 1.0 - ml_risk_score
                                    
                                    # Get Kelly Mult based on prob and target R:R (1.5)
                                    acc = mt5_client.account_info()
                                    current_dd = 0.0
                                    if acc:
                                        account_peak = max(account_peak, float(acc.balance))
                                        current_dd = (account_peak - float(acc.balance)) / account_peak
                                        
                                    bayesian_mult = kelly_engine.calculate_sizing_multiplier(prob_success, reward_risk=1.5, current_dd=current_dd)
                                    
                                    if ml_risk_score > 0.75:
                                        logger.warning(f"🛑 [5/7] ML BLOCKED: {pair} Risk={ml_risk_score:.2f} (High Stop-Hunt Probability)")
                                        continue
                                    
                                    if bayesian_mult <= 0:
                                        logger.warning(f"⚖️ [5/7] KELLY SKIP: {pair} No mathematical edge detected (f* <= 0).")
                                        continue

                                    logger.info(f"✅ [5/7] ML CALIBRATED: {pair} Prob={prob_success:.2f} | Kelly Mult={bayesian_mult:.2f}x")
                                except Exception as e:
                                    logger.error(f"⚠️ ML/Kelly Error: {e}")
                            else:
                                logger.info(f"⚖️ [4/7] KELLY: ML Disabled, using neutral 1.0x")

                        # --- EXECUTION ---
                        # Mark as signaled for today
                        last_signal_date[pair] = current_date
                        
                        # --- PHASE 14: INSTITUTIONAL RISK CHECK ---
                        # 3. Institutional Risk Check
                        order_type = "BS (Buy Stop)" if sig == 1 else "SS (Sell Stop)"
                        if not check_correlation_exposure(pair, order_type):
                            logger.warning(f"🛑 [4/5] RISK BLOCKED: Correlation/Cap limit for {pair}")
                            continue 
                        logger.info(f"✅ [4/5] RISK PASSED: {pair} (Portfolio sync OK)")

                        # Calculate Dynamic Risk
                        daily_start = current_capital # Fallback
                        equity = current_capital
                        if MT5_CONNECTED:
                            acc = mt5_client.account_info()
                            if acc:
                                daily_start = acc.balance 
                                equity = acc.equity
                        
                        current_atr = row['atr']
                        avg_atr = data['atr'].mean()
                        base_risk = calculate_institutional_risk(current_capital, daily_start, equity, current_atr, avg_atr, RISK_PER_TRADE)
                        
                        # Apply Probabilistic Sizing: Adjust by confidence, regime and bayesian conviction
                        regime_multiplier = 1.0 if regime == "TRENDING" else 0.75
                        RISK_APPLIED = base_risk * confidence_factor * regime_multiplier * bayesian_mult
                        
                        RR_TARGET = 1.5
                        print(f"📉 DYNAMIC RISK: {RISK_APPLIED*100:.3f}% | Trigger: {pair} {order_type}")
                        hive_tag = "🌟 GOLDEN SNIPER (H1)"
                        
                        # Stops
                        current_atr = row['atr']
                        current_price = row['close']
                        sl_dist = current_atr * 2.0
                        tp_dist = sl_dist * RR_TARGET
                        
                        if sig == 1:
                            sl = current_price - sl_dist
                            tp = current_price + tp_dist
                        else:
                            sl = current_price + sl_dist
                            tp = current_price - tp_dist
                            
                        # Log Logic
                        logging.info(f"✅ HIVE V5 TRIGGER: {pair} | ADX={adx_val:.1f} | Vol={current_vol:.1f} | Target={RR_TARGET}R")

                        # Def order type for alert
                        order_type = "BS (Buy Stop)" if sig == 1 else "SS (Sell Stop)"
                        
                        # Risk Amount
                        sl_diff = abs(current_price - sl)
                        risk_usd = current_capital * RISK_APPLIED 
                        
                        # LOT SIZE CALCULATION
                        lot_str = "0.01 Lots"
                        execution_volume = 0.01
                        
                        if "USD" in pair and "BTC" not in pair and "SOL" not in pair:
                            sl_pips = sl_diff * 10000
                            if "JPY" in pair: sl_pips = sl_diff * 100
                            if sl_pips > 0:
                                lots = risk_usd / (sl_pips * 10.0)
                            else: lots = 0
                            lot_str = f"{lots:.2f} Lots"
                            execution_volume = round(lots, 2)
                            
                        elif "BTC" in pair or "SOL" in pair:
                            if sl_diff > 0:
                                units = risk_usd / sl_diff
                            else: units = 0
                            lot_str = f"{units:.2f} Coins"
                            execution_volume = round(units, 2)
                        
                        # Send Alert
                        msg = (f"🚀 *HIVE V5 SIGNAL* 🚀\n"
                               f"Pair: *{pair}*\n"
                               f"Action: *{order_type}*\n"
                               f"Price: *{current_price:.4f}*\n"
                               f"SL: *{sl:.4f}*\n"
                               f"TP: *{tp:.4f}* (3R)\n"
                               f"Risk: ${risk_usd:.2f} ({RISK_APPLIED*100:.1f}%)\n"
                               f"Size: *{lot_str}*\n"
                               f"Stats: ADX={adx_val:.1f} | Vol={current_vol:.1f}\n"
                               f"Valid Until: End of Day")
                               
                        print(f"\n🔥 SIGNAL: {pair} {order_type} @ {current_price:.4f} | Size: {lot_str}")
                        
                        # --- PHASE 17: RL GATEKEEPER ("The Chooser") 🛡️ ---
                        gk_signal_valid = True
                        if gatekeeper_agent and GATEKEEPER_MODE != "OFF":
                            try:
                                # Fetch 50 candles for feature engineering (Strict Match to Training)
                                gk_rates = mt5_client.copy_rates_from_pos(symbol, mt5_client.TIMEFRAME_H1, 0, 50)
                                if gk_rates is not None and len(gk_rates) > 30:
                                    gk_df = pd.DataFrame(gk_rates)
                                    gk_close = gk_df['close']; gk_high = gk_df['high']; gk_low = gk_df['low']
                                    
                                    # 0. ATR (Essential for normalization)
                                    gk_tr = pd.concat([gk_high-gk_low, abs(gk_high-gk_close.shift(1)), abs(gk_low-gk_close.shift(1))], axis=1).max(axis=1)
                                    gk_atr = gk_tr.rolling(14).mean().iloc[-1]
                                    if gk_atr == 0: gk_atr = 0.0001

                                    # 1. EMA Slope (Normalized by ATR, Diff 3)
                                    gk_ema = gk_close.ewm(span=9, adjust=False).mean()
                                    gk_slope_norm = (gk_ema.iloc[-1] - gk_ema.iloc[-4]) / gk_atr

                                    # 2. Volatility (StdDev(24) * 1000)
                                    gk_returns = gk_close.pct_change()
                                    gk_vol = gk_returns.rolling(24).std().iloc[-1] * 1000
                                    
                                    # 3. ATR Norm (ATR / Close)
                                    gk_atr_norm = gk_atr / gk_close.iloc[-1]

                                    # Predict
                                    gk_action, gk_conf = gatekeeper_agent.predict(gk_slope_norm, gk_vol, gk_atr_norm)
                                    
                                    gate_msg = f"🛡️ GATEKEEPER: {'ACCEPT' if gk_action==1 else 'REJECT'} ({gk_conf:.2f}) | Fts: Slope={gk_slope_norm:.2f} Vol={gk_vol:.1f}"
                                    logger.info(gate_msg)
                                    
                                    # Ensure bot instance exists
                                    try: 
                                        bot = TelegramBot() 
                                    except: 
                                        class bot: enabled=False

                                    if gk_action == 0:
                                        if GATEKEEPER_MODE == "ACTIVE":
                                            logger.warning(f"🛑 BLOCKED BY GATEKEEPER")
                                            if bot.enabled: bot.send_message(f"🛑 *BLOCKED BY GATEKEEPER*\n{gate_msg}")
                                            gk_signal_valid = False
                                        elif GATEKEEPER_MODE == "SHADOW":
                                            if bot.enabled: bot.send_message(f"👻 *SHADOW*: Would have BLOCKED\n{gate_msg}")

                            except Exception as e:
                                logger.error(f"Gatekeeper Logic Error: {e}")

                        if not gk_signal_valid:
                            continue

                        # --- PHASE 71: AUTO EXECUTION ---
                        if MT5_CONNECTED:
                            logger.info(f"🦖 [5/5] EXECUTING ORDER: {pair} @ {current_price:.4f}")
                            # Use 2.0 pip buffer for entry if desired, but strategy says BS/SS at current?
                            # Actually pending order usually needs offset. 
                            # If Buy Stop, Price > Current. 
                            # The code calculated sl/tp based on 'current_price'.
                            # If we send PENDING, it must be away from market.
                            # HIVE V5 manual says "Pending Orders".
                            # Let's assume we want to enter *at* the signal price (Retracement?)
                            # Or capture the breakout.
                            # For now, let's place it at 'current_price' which forces Market execution if immediate,
                            # or use logic for buffer?
                            # "PENDING_ORDER_BUFFER_PIPS = 2.0" exists.
                            
                            entry_price = current_price
                            if "BS" in order_type:
                                entry_price += (PENDING_ORDER_BUFFER_PIPS * 0.0001)
                                if "JPY" in pair: entry_price += (PENDING_ORDER_BUFFER_PIPS * 0.01)
                            else:
                                entry_price -= (PENDING_ORDER_BUFFER_PIPS * 0.0001)
                                if "JPY" in pair: entry_price -= (PENDING_ORDER_BUFFER_PIPS * 0.01)

                            # Recalculate SL/TP based on new entry? 
                            # Or keep original structure? 
                            # Strategy says: SL dist based on ATR. 
                            # Let's keep distinct SL distance.
                            
                            # Execute
                            execute_mt5_trade(pair, order_type, entry_price, sl, tp, execution_volume)

                        try:
                            if 'bot' in locals() and bot.enabled: bot.send_message(msg)
                        except: pass
                        
                except Exception as e:
                    logger.error(f"Iter Error: {e}")
                    pass # subtle error suppression for loop stability
                    
            time.sleep(60)
            
        except KeyboardInterrupt:
            print("\n🛑 Stopped.")
            if MT5_CONNECTED:
                mt5_client.shutdown()
                print("🍏 Silicon MT5 Disconnected.")
            break
        except Exception as e:
            logger.error(f"Loop error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
