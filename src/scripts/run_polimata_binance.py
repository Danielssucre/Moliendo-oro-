#!/usr/bin/env python3
"""
🧠 POLIMATA BINANCE CORE ⚡
====================================
Live trading bot using DQN Reinforcement Learning to select strategies.
Capital: 11 slots of ~$5.10 USDT each (based on $56.91 balance)
Pairs: ETHUSDT, SOLUSDT
"""

import sys
import os
import time
import logging
import json
import pandas as pd
import numpy as np
from datetime import datetime
import math

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
sys.path.insert(0, _PROJECT_ROOT)

from src.nanobot.exchanges.binance_client import BinanceClient
from binance.exceptions import BinanceAPIException
from stable_baselines3 import DQN

# --- LOGGING ---
LOG_DIR = os.path.join(_PROJECT_ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'polimata_binance.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Polimata.Binance")

# --- TELEGRAM ---
from src.nanobot.utils.telegram_bot import TelegramBot
bot = TelegramBot()

def tg(msg: str):
    if not bot.enabled: return
    bot.send_message(msg)

# --- CONFIG ---
# Symbols must match the indices in Polimata's brain
SYMBOLS_MAP = {
    "ETHUSDT": 3,
    "SOLUSDT": 12,
    "BTCUSDT": 1
}
ACTIVE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
SCAN_INTERVAL  = 60
MIN_NOTIONAL   = 18.0  # Distributed: $60 / 3 slots = ~$20 per entry
MAX_SLOTS      = 3     # 1 per core asset

# --- POLIMATA MODEL ---
MODEL_PATH = os.path.join(_PROJECT_ROOT, "models/polimata_rl_v1.zip")
ACTIONS_MAP = {0: 'SKIP', 1: 'ALFA', 2: 'EXPLORATION', 3: 'NEMESIS'}

# --- BANK PRIORITY ---
BANK_PRIORITY_MODE    = True
DEBT_MONTHLY_TARGET   = 31.50
CAPITAL_INITIAL       = 60.0
last_notified_target  = False

# --- STRATEGY PARAMETERS (Block specific) ---
BLOCK_CONFIGS = {
    'ALFA':        {'tp': 0.015, 'sl': 0.012, 'desc': 'Trend Sniper'},
    'EXPLORATION': {'tp': 0.050, 'sl': 0.020, 'desc': 'Trend Runner'},
    'NEMESIS':     {'tp': 0.012, 'sl': 0.015, 'desc': 'Mean Reversion'}
}

class PolimataBinance:
    def __init__(self):
        self.client = BinanceClient()
        self.model = self._load_model()
        self.active_positions = {} # {ticket_id: {symbol, entry, qty, block, ...}}
        self.slots_used = 0

    def _load_model(self):
        if not os.path.exists(MODEL_PATH):
            logger.error(f"❌ Polimata brain missing at {MODEL_PATH}!")
            sys.exit(1)
        logger.info(f"🧠 Loading Polimata Neural Pathways from {os.path.basename(MODEL_PATH)}...")
        return DQN.load(MODEL_PATH)

    def get_prediction(self, symbol):
        if symbol not in SYMBOLS_MAP: return 'SKIP'
        
        hour = datetime.now().hour
        sym_idx = SYMBOLS_MAP[symbol]
        
        # State: [Hour, SymbolIndex]
        obs = np.array([hour, sym_idx], dtype=np.float32)
        action, _ = self.model.predict(obs, deterministic=True)
        
        return ACTIONS_MAP.get(int(action), 'SKIP')

    def recover_state(self):
        """Recover existing positions from exchange."""
        logger.info("🔍 RECOVERY MODE: Scanning for active slots...")
        for sym in ACTIVE_SYMBOLS:
            asset = sym.replace("USDT", "")
            bal = self.client.get_balance(asset)
            
            # Check Earn
            earn_bal = self.client.get_balance(f"LD{asset}")
            if earn_bal > 0:
                logger.info(f"   🛠️ Rescuing {earn_bal} {asset} from Earn...")
                self.client.redeem_from_savings(asset, earn_bal)
                bal += earn_bal

            if bal * self.get_price(sym) > 1.0: # Non-dust
                try:
                    trades = self.client.client.get_my_trades(symbol=sym, limit=5)
                    if trades:
                        last_buy = [t for t in trades if t['isBuyer']][-1]
                        entry = float(last_buy['price'])
                        # We don't know the block from past, default to ALFA
                        self.active_positions[sym] = {
                            "entry": entry, "qty": bal, "block": "ALFA", "recovered": True
                        }
                        self.slots_used += 1
                        logger.info(f"   ✅ Recovered {sym} @ ${entry:.2f} (Slot {self.slots_used})")
                except Exception as e:
                    logger.error(f"   ❌ Error recovering {sym}: {e}")

    def get_price(self, symbol):
        return float(self.client.client.get_symbol_ticker(symbol=symbol)['price'])

    def run_cycle(self):
        loop_time = datetime.now().strftime('%H:%M:%S')
        logger.info(f"--- POLIMATA CYCLE {loop_time} | Slots: {self.slots_used}/{MAX_SLOTS} | {list(self.active_positions.keys())} ---")
        
        # 0. Calculate Dynamic Slot Size
        try:
            total_usdt = self.client.get_total_balance("USDT")
            invested = 0
            for s in self.active_positions:
                invested += self.active_positions[s]['qty'] * self.get_price(s)
            
            equity = total_usdt + invested
            # Split equity in MAX_SLOTS with 5% safety buffer for fees/slippage
            self.dynamic_slot_size = (equity * 0.95) / MAX_SLOTS
            
            # Clamp to Binance floor (5.0) + slight buffer
            if self.dynamic_slot_size < 5.10: 
                self.dynamic_slot_size = 5.10
                
            logger.info(f"📊 Equity: ${equity:.2f} | Dynamic Slot Size: ${self.dynamic_slot_size:.2f}")
        except Exception as e:
            logger.error(f"Error calculating dynamic slots: {e}")
            self.dynamic_slot_size = MIN_NOTIONAL # Fallback

        # 1. Basket Profit Lock (Equity Protection)
        self.check_basket_profit_lock()

        # 1. Prune Zombie Positions (Sanity Check)
        self.prune_positions()
        for sym in list(self.active_positions.keys()):
            pos = self.active_positions[sym]
            price = self.get_price(sym)
            pnl_pct = (price - pos['entry']) / pos['entry']
            
            config = BLOCK_CONFIGS[pos['block']]
            
            # Check TP/SL
            if pnl_pct >= config['tp'] or pnl_pct <= -config['sl']:
                reason = "TP" if pnl_pct > 0 else "SL"
                logger.info(f"💰 Closing {sym} ({reason}) | P&L: {pnl_pct*100:.2f}%")
                self.close_position(sym, price)

        # 2. Scan for New Entries
        usdt = self.client.get_balance("USDT")
        
        # Auto-redeem Earn USDT
        earn_usdt = self.client.get_balance('LDUSDT')
        if earn_usdt > 0:
            logger.info(f"💰 Redeeming {earn_usdt} USDT from Savings...")
            self.client.redeem_from_savings('USDT', earn_usdt)
            time.sleep(2) # Give Binance a moment to reflect balance in Spot
            usdt = self.client.get_balance("USDT")

        if self.slots_used < MAX_SLOTS and usdt >= self.dynamic_slot_size:
            for sym in ACTIVE_SYMBOLS:
                if sym in self.active_positions: continue
                if self.slots_used >= MAX_SLOTS: break

                block = self.get_prediction(sym)
                if block != 'SKIP':
                    logger.info(f"🧠 Polimata recommends {block} for {sym}. Opening Slot...")
                    self.open_position(sym, block)

    def open_position(self, symbol, block):
        try:
            price = self.get_price(symbol)
            qty = self.dynamic_slot_size / price
            # Precision lookup: based on Binance LOT_SIZE stepSize
            if "BTC" in symbol: precision = 5
            elif "ETH" in symbol: precision = 4
            elif "SOL" in symbol: precision = 3
            else: precision = 2
            
            qty = math.floor(qty * (10**precision)) / (10**precision)

            order = self.client.market_buy(symbol, qty)
            actual_price = float(order['fills'][0]['price']) if 'fills' in order else price
            
            self.active_positions[symbol] = {
                "entry": actual_price, "qty": qty, "block": block
            }
            self.slots_used += 1
            
            tg(f"🧠 *Polimata Entry* | `{symbol}`\n"
               f"━━━━━━━━━━━━━━\n"
               f"⚡ Block: `{block}`\n"
               f"💰 Slot: `{self.slots_used}/{MAX_SLOTS}`\n"
               f"📌 Entry: `${actual_price:.2f}`")
            
        except Exception as e:
            logger.error(f"❌ Entry Error {symbol}: {e}")

    def close_position(self, symbol, price):
        try:
            if symbol not in self.active_positions: return
            pos = self.active_positions[symbol]
            asset = symbol.replace("USDT", "")
            
            # Fetch actual live balance to account for fees subtracted during entry
            actual_bal = self.client.get_balance(asset)
            
            # Notional check before attempting market sell
            notional_value = actual_bal * price
            if notional_value < 5.05: # Binance floor is 5.0
                logger.warning(f"⚠️ {symbol} Notional value (${notional_value:.2f}) is too small for standard exit. It is now dust.")
                tg(f"⚠️ *Dust Alert* | `{symbol}`\n"
                   f"The remaining value (${notional_value:.2f}) is below Binance minimum ($5.00).\n"
                   f"It will be cleared from tracking. Manual conversion to BNB recommended.")
                if symbol in self.active_positions:
                    del self.active_positions[symbol]
                    self.slots_used = len(self.active_positions)
                return

            # Execute sell with actual balance
            self.client.market_sell(symbol, actual_bal)
            
            pnl_val = (price - pos['entry']) * actual_bal
            pnl_pct = (price - pos['entry']) / pos['entry'] * 100
            
            tg(f"🏁 *Polimata Exit* | `{symbol}`\n"
               f"━━━━━━━━━━━━━━\n"
               f"📈 P&L: `{pnl_pct:+.2f}%` (${pnl_val:+.4f})\n"
               f"🏦 Result: {'✅ PROFIT' if pnl_pct > 0 else '🛑 LOSS'}")
            
            if symbol in self.active_positions:
                del self.active_positions[symbol]
                self.slots_used = len(self.active_positions)
        except Exception as e:
            logger.error(f"❌ Exit Error {symbol}: {e}")
            if "NOTIONAL" in str(e) or "Filter failure" in str(e):
                logger.warning(f"⚠️ Forcing prune for {symbol} due to filter failure.")
                if symbol in self.active_positions:
                    del self.active_positions[symbol]
                    self.slots_used = len(self.active_positions)

    def check_basket_profit_lock(self):
        """Checks if the combined floating profit exceeds the threshold and closes all if enabled."""
        config_path = os.path.join(_PROJECT_ROOT, "config/basket_config.json")
        if not os.path.exists(config_path): return

        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            if not config.get('enabled', False): return
            
            threshold = config.get('threshold', 5.0)
            total_pnl = 0
            
            # Use symbols from SYMBOLS_MAP to be safe
            for sym in list(self.active_positions.keys()):
                pos = self.active_positions[sym]
                current_price = self.get_price(sym)
                if current_price > 0:
                    total_pnl += (current_price - pos['entry']) * pos['qty']
            
            if total_pnl >= threshold:
                logger.info(f"🚀 BASKET PROFIT LOCK TRIGGERED! Total P&L: ${total_pnl:.2f} >= ${threshold:.2f}")
                tg(f"🚀 BASKET PROFIT LOCK TRIGGERED! Total P&L: ${total_pnl:.2f}")
                for sym in list(self.active_positions.keys()):
                    self.close_position(sym, self.get_price(sym))
                
                # Update last_trigger log (optional)
                config['last_trigger'] = datetime.now().isoformat()
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=4)
        except Exception as e:
            logger.error(f"Error checking basket lock: {e}")

    def prune_positions(self):
        """Verify that all internal active positions actually have a corresponding balance in Binance."""
        for sym in list(self.active_positions.keys()):
            asset = sym.replace("USDT", "")
            bal = self.client.get_total_balance(asset)
            price = self.get_price(sym)
            
            # If balance dropped below $1.0 equivalent, the position is considered closed or zombie
            if bal * price < 1.0:
                logger.warning(f"⚠️  PRUNING: Position {sym} appears closed (Bal: {bal}). Clearing Slot.")
                del self.active_positions[sym]
                self.slots_used = max(0, self.slots_used - 1)

def main():
    bot = PolimataBinance()
    bot.recover_state()
    
    tg("🤖 *POLIMATA BINANCE CORE IS ONLINE* 🧠\n"
       f"Capacity: {MAX_SLOTS} Diversified Slots\n"
       "Asset Knowledge: ETH, SOL, BTC assimilated.")

    while True:
        try:
            bot.run_cycle()
            time.sleep(SCAN_INTERVAL)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"🔥 Core Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
