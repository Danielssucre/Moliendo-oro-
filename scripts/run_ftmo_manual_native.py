#!/usr/bin/env python3
"""
NANOBOT FTMO MANUAL EXECUTION BOT (Phase 29)
- Portfolio: SOL, AUD, NZD, BTC, GBP (The Big 5)
- Risk: 0.2% per trade (Prop Firm Safe)
- Mode: Manual Signaling (Pending Orders)
- Schedule: 24/7 Vigilance
"""
import sys
import os
import time
import logging
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.utils.telegram_bot import TelegramBot
except ImportError:
    class TelegramBot: # Fallback dummy
        enabled = False
        def send_message(self, msg): print(f"TELEGRAM MOCK: {msg}")

# Import ML Model
try:
    from src.ml.stop_hunt_model import StopHuntModel
    ML_ENABLED = True
except ImportError:
    ML_ENABLED = False
    print("⚠️ ML Module not found. Running in Technical Mode only.")

import argparse

# --- ARGS ---
parser = argparse.ArgumentParser(description='Nanobot FTMO Manual')
parser.add_argument('--capital', type=float, default=10000, help='Account Balance')
args = parser.parse_args()

# --- CONFIGURATION ---
INITIAL_CAPITAL = args.capital
current_capital = INITIAL_CAPITAL # Dynam# Risk Management (Updated Phase 45: "Fast FTMO")
RISK_PER_TRADE = 0.004 # 0.4% (Scientific Sweet Spot)

# Asset Mapping (HIVE V5 ALL-STARS)
# Top 11 Performers from "Expansion Scan" (Profit > $300)
ASSET_MAP = {
    "AUDUSD": "AUDUSD=X",  # King ($1560)
    "GBPJPY": "GBPJPY=X",  # Beast ($1260)
    "BTCUSD": "BTC-USD",   # Crypto ($1140)
    "SOLUSD": "SOL-USD",   # Crypto ($1140)
    "NZDUSD": "NZDUSD=X",  # Core ($1080)
    "USDCHF": "USDCHF=X",  # Swissy ($780)
    "EURNZD": "EURNZD=X",  # Cross ($540)
    "GBPUSD": "GBPUSD=X",  # Cable ($480)
    "GBPNZD": "GBPNZD=X",  # Cross ($480)
    "USDJPY": "USDJPY=X",  # Ninja ($360)
    "USDCAD": "USDCAD=X"   # Loonie ($360)
}
PENDING_ORDER_BUFFER_PIPS = 2.0
LIMIT_ORDER_RETRACT_PIPS = 3.0

# Setup logging (Console + File)
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
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

def main():
    print(f"""
    ╔══════════════════════════════════════════════════════╗
    ║   🦖 NANOBOT HIVE V5 (ALL-STARS EDITION) 🌟          ║
    ║   Assets: Top 11 Performers (AUD, GBP, JPY, Crypto)  ║
    ║   Mode:   DAILY RE-ENTRY (Golden Trends)             ║
    ║   Risk:   0.6% (Sniper Mode)                         ║
    ║   Capital: ${current_capital:,.2f}                     ║
    ╚══════════════════════════════════════════════════════╝
    """)
    
    # Telegram Startup
    try:
        bot = TelegramBot()
        if bot.enabled:
            bot.send_message("🦖 *HIVE V5 ALL-STARS LIVE* 🟢\nLoaded Top 11 Pairs.\nScanning for Daily Golden Setups...")
    except: pass
    
    logger.info("⚡ Entering 24/7 Signal Scan Loop...")
    
    # Track sent signals to enforce DAILY RE-ENTRY
    # {pair: 'YYYY-MM-DD'}
    last_signal_date = {} 
    
    print(f"⏳ Scanning... (Ctrl+C to stop)")
    
    while True:
        try:
            # Check for AI Retraining
            check_auto_retrain()
            
            timestamp_str = datetime.now().strftime('%H:%M:%S')
            print(f"\r⏳ Scanning... {timestamp_str} UTC | AI: {'ACTIVE' if stop_hunt_model else 'OFF'}", end="")
            
            for pair in ASSET_MAP.keys():
                symbol = ASSET_MAP.get(pair)
                try:
                    # Use Ticker.history for better single-symbol stability
                    ticker = yf.Ticker(symbol)
                    data = ticker.history(period="5d", interval="15m")
                    
                    if data.empty: continue
                    data.columns = data.columns.str.lower()
                    if len(data) < 50: continue
                    
                    sig, strategy, row = analyze_hybrid_signal(data)
                    
                    if sig != 0:
                        # --- DAILY RE-ENTRY CHECK ---
                        current_date = datetime.now().strftime("%Y-%m-%d")
                        last_date = last_signal_date.get(pair)
                        
                        if last_date == current_date:
                            # Already signaled today for this pair
                            continue
                            
                        # --- HIVE V5 FILTERS ---
                        # 1. Calculate Volatility
                        try:
                            returns = data['close'].pct_change()
                            current_vol = (returns.rolling(24).std() * 1000).iloc[-1]
                        except: current_vol = 20.0
                        
                        adx_val = row['adx']
                        
                        # SILENCER: Golden Setup Only
                        if not (adx_val > 27 and current_vol < 16):
                            # Log every 10 mins or so to avoid spam? 
                            # Actually, standard log is fine, user knows.
                            logging.info(f"🚫 HIVE V5 FILTER: {pair} REJECTED. (ADX={adx_val:.1f}, Vol={current_vol:.1f}). Need >27/<16.")
                            continue 
                            
                        # --- ML CHECK (Optional) ---
                        ml_risk_score = 0.0
                        if ML_ENABLED and stop_hunt_model:
                            try:
                                features = stop_hunt_model.extract_features(data, row['close'], {'rsi': row['rsi'], 'adx': row['adx'], 'atr': row['atr'], 'vwap': row['close']})
                                ml_risk_score = stop_hunt_model.predict_risk(features)
                                if ml_risk_score > 0.65:
                                    logger.warning(f"🛑 ML BLOCKED: {pair} Risk={ml_risk_score:.2f}")
                                    continue
                            except: pass

                        # --- EXECUTION ---
                        # Mark as signaled for today
                        last_signal_date[pair] = current_date
                        
                        RISK_APPLIED = 0.003 # 0.3% (Safety Adjustment for 11 Pairs)
                        RR_TARGET = 3.0
                        hive_tag = "🌟 GOLDEN SNIPER (V5)"
                        
                        # Stops
                        current_atr = row['atr']
                        current_price = row['close']
                        sl_dist = current_atr * 1.5
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
                        if "USD" in pair and "BTC" not in pair and "SOL" not in pair:
                            sl_pips = sl_diff * 10000
                            if "JPY" in pair: sl_pips = sl_diff * 100
                            if sl_pips > 0:
                                lots = risk_usd / (sl_pips * 10.0)
                            else: lots = 0
                            lot_str = f"{lots:.2f} Lots"
                        elif "BTC" in pair or "SOL" in pair:
                            if sl_diff > 0:
                                units = risk_usd / sl_diff
                            else: units = 0
                            lot_str = f"{units:.2f} Coins"
                        
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
                        try:
                            if 'bot' in locals() and bot.enabled: bot.send_message(msg)
                        except: pass
                        
                except Exception as e:
                    pass # subtle error suppression for loop stability
                    
            time.sleep(60)
            
        except KeyboardInterrupt:
            print("\n🛑 Stopped.")
            break
        except Exception as e:
            logger.error(f"Loop error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
