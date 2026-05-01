#!/usr/bin/env python3
"""
🛰️ NEME SPOT BINANCE ⚡
====================================
Estrategia NEMESIS (Mean Reversion) extrapolada a Binance Spot.
Solo opera LARGOS (Reversión desde suelo).
"""

import sys
import os
import time
import logging
import json
import pandas as pd
import numpy as np
import math
from datetime import datetime

# Setup Paths
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
sys.path.insert(0, _PROJECT_ROOT)

from src.nanobot.exchanges.binance_client import BinanceClient
from src.analysis.indicators import IndicatorAnalyzer
from src.nanobot.strategies.forex_infantry import ForexInfantry
from src.nanobot.utils.telegram_bot import TelegramBot

# --- LOGGING ---
LOG_DIR = os.path.join(_PROJECT_ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'neme_binance_spot.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("NEME.Binance")

# --- CONFIG ---
ACTIVE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
SCAN_INTERVAL  = 60
MAX_SLOTS      = 3  # Foco quirúrgico
ATR_SL_MULT    = 1.5
ATR_TP_MULT    = 2.25

class NemeBinanceSpot:
    def __init__(self):
        self.client = BinanceClient()
        self.engine = ForexInfantry()
        self.tg = TelegramBot()
        self.active_positions = {} # {symbol: {entry, qty, sl, tp, strategy}}
        self.slots_used = 0
        self.dynamic_slot_size = 15.0 # Fallback

    def notify(self, msg: str):
        if self.tg.enabled:
            self.tg.send_message(msg)

    def get_price(self, symbol):
        return self.client.get_price(symbol)

    def run_cycle(self):
        loop_time = datetime.now().strftime('%H:%M:%S')
        logger.info(f"--- NEME CYCLE {loop_time} | Slots: {self.slots_used}/{MAX_SLOTS} | {list(self.active_positions.keys())} ---")

        # 1. Update Equity & Dynamic Slot
        try:
            total_usdt = self.client.get_total_balance("USDT")
            invested = 0
            for s in self.active_positions:
                invested += self.active_positions[s]['qty'] * self.get_price(s)
            
            equity = total_usdt + invested
            self.dynamic_slot_size = (equity * 0.95) / MAX_SLOTS
            if self.dynamic_slot_size < 10.50: self.dynamic_slot_size = 10.50
            logger.info(f"📊 Equity: ${equity:.2f} | Dynamic Slot: ${self.dynamic_slot_size:.2f}")
        except Exception as e:
            logger.error(f"Error updating slots: {e}")

        # 2. Manage Active Positions (TP/SL)
        for sym in list(self.active_positions.keys()):
            pos = self.active_positions[sym]
            price = self.get_price(sym)
            
            # Use same logic as Forex: SL < Entry < TP for Longs
            if price >= pos['tp']:
                logger.info(f"💰 [NEME TP] Closing {sym} | Price: {price} | Profit: {((price/pos['entry'])-1)*100:.2f}%")
                self.close_position(sym, price, "TAKE_PROFIT")
            elif price <= pos['sl']:
                logger.info(f"🛑 [NEME SL] Closing {sym} | Price: {price} | Loss: {((price/pos['entry'])-1)*100:.2f}%")
                self.close_position(sym, price, "STOP_LOSS")

        # 3. Scan for New NEME Signals
        if self.slots_used < MAX_SLOTS:
            for sym in ACTIVE_SYMBOLS:
                if sym in self.active_positions: continue
                if self.slots_used >= MAX_SLOTS: break

                try:
                    # Fetch H1 for analysis (same as Forex engine)
                    klines = self.client.get_klines(sym, interval="1h", limit=300)
                    df = pd.DataFrame(klines, columns=['time','open','high','low','close','volume','ct','qv','tr','tb','tq','i'])
                    df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].apply(pd.to_numeric)
                    
                    analyzer = IndicatorAnalyzer(df)
                    inds = analyzer.get_latest_values()
                    
                    # Compute NEME Signal
                    signal_df = analyzer.df.copy()
                    neme_sig, strat_name = self.engine.get_nemesis_signal_with_strategy(signal_df)
                    
                    # EXTRAPOLATION RULE: In Spot, we only take the BUY signals (neme_sig == 1)
                    if neme_sig == 1:
                        logger.info(f"Targets: Signal={neme_sig} | Strategy={strat_name} for {sym}")
                        self.open_position(sym, neme_sig, strat_name, inds)
                    
                except Exception as e:
                    logger.error(f"Error scanning {sym}: {e}")

    def open_position(self, symbol, signal, strategy, inds):
        try:
            price = self.get_price(symbol)
            qty = self.dynamic_slot_size / price
            
            # ATR-Based Levels
            atr = inds.get('atr', price * 0.02) # Fallback 2%
            sl = price - (atr * ATR_SL_MULT)
            tp = price + (atr * ATR_TP_MULT)

            # Precision
            if "BTC" in symbol: precision = 5
            elif "ETH" in symbol: precision = 4
            else: precision = 2
            qty = math.floor(qty * (10**precision)) / (10**precision)

            order = self.client.market_buy(symbol, qty)
            actual_price = float(order['fills'][0]['price']) if 'fills' in order else price
            
            self.active_positions[symbol] = {
                "entry": actual_price, "qty": qty, "sl": sl, "tp": tp, "strategy": strategy
            }
            self.slots_used += 1
            
            self.notify(f"🚀 *NEME Spot Entry* | `{symbol}`\n"
                       f"━━━━━━━━━━━━━━\n"
                       f"🧠 Strategy: `{strategy}`\n"
                       f"📌 Entry: `${actual_price:.2f}`\n"
                       f"🛑 SL: `${sl:.2f}` | 🎯 TP: `${tp:.2f}`")
            
        except Exception as e:
            logger.error(f"❌ Entry Error {symbol}: {e}")

    def close_position(self, symbol, price, reason):
        try:
            pos = self.active_positions[symbol]
            asset = symbol.replace("USDT", "")
            actual_bal = self.client.get_balance(asset)
            
            if actual_bal * price < 5.0:
                logger.warning(f"Dust detected on {symbol}. Clearing.")
            else:
                self.client.market_sell(symbol, actual_bal)
            
            pnl_pct = (price - pos['entry']) / pos['entry'] * 100
            
            self.notify(f"🏁 *NEME Spot Exit* | `{symbol}`\n"
                       f"━━━━━━━━━━━━━━\n"
                       f"📈 P&L: `{pnl_pct:+.2f}%`\n"
                       f" motivos: `{reason}` | {pos['strategy']}")
            
            if symbol in self.active_positions:
                del self.active_positions[symbol]
                self.slots_used = len(self.active_positions)
        except Exception as e:
            logger.error(f"❌ Exit Error {symbol}: {e}")

def main():
    bot = NemeBinanceSpot()
    logger.info("⚡ NEME BINANCE SPOT ONLINE 🧠")
    while True:
        try:
            bot.run_cycle()
            time.sleep(SCAN_INTERVAL)
        except KeyboardInterrupt: break
        except Exception as e:
            logger.error(f"🔥 Loop Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
