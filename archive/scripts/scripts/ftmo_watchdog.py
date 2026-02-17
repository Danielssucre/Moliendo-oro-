#!/usr/bin/env python3
import sys
import os
import time
import logging
from datetime import datetime
from pathlib import Path

# Silicon MT5 Integration
try:
    from siliconmetatrader5 import MetaTrader5
    mt5 = MetaTrader5(port=8001)
except ImportError:
    print("❌ siliconmetatrader5 not found")
    sys.exit(1)

# Telegram
try:
    # Adding parent to path to find src
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.utils.telegram_bot import TelegramBot
    telegram = TelegramBot()
except ImportError:
    class TelegramBot: 
        enabled = False
        def send_message(self, m): print(f"TELEGRAM: {m}")
    telegram = TelegramBot()

# --- CONFIG ---
MAX_DAILY_LOSS_PCT = 4.5  # Safety margin (FTMO is 5%)
MAX_TOTAL_LOSS_PCT = 9.0   # Safety margin (FTMO is 10%)
HEARTBEAT_MINUTES = 60    # Stay-alive notification frequency
CHECK_INTERVAL_SEC = 5    # Vigilance frequency

def get_initial_balance():
    # In a real scenario, this would be fetched from a DB or specific config
    # For FTMO Phase 1 $10k, we hardcode or fetch on first run.
    return 10000.0

def emergency_stop(reason):
    print(f"🚨 CRITICAL: EMERGENCY STOP TRIGGERED! Reason: {reason}")
    telegram.send_message(f"🚨 *CRITICAL EMERGENCY STOP* 🚨\nReason: {reason}\nLiquidating all positions...")
    
    # 1. Close all open positions
    positions = mt5.positions_get()
    if positions:
        for p in positions:
            print(f"🛑 Closing Position #{p.ticket} ({p.symbol})")
            # Create close request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": p.symbol,
                "volume": p.volume,
                "type": mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                "position": p.ticket,
                "price": mt5.symbol_info_tick(p.symbol).bid if p.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(p.symbol).ask,
                "deviation": 20,
                "magic": p.magic,
                "comment": "WATCHDOG KILL SWITCH",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            res = mt5.order_send(request)
            if res.retcode != mt5.TRADE_RETCODE_DONE:
                telegram.send_message(f"⚠️ Failed to close position #{p.ticket}: {res.comment}")

    # 2. Cancel all pending orders
    orders = mt5.orders_get()
    if orders:
        for o in orders:
            print(f"🚫 Cancelling Order #{o.ticket}")
            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": o.ticket,
                "comment": "WATCHDOG KILL SWITCH"
            }
            res = mt5.order_send(request)

    telegram.send_message("✅ Account successfully liquidated. Trading disabled.")
    # Exit script to stop further loops
    sys.exit(0)

def main():
    print("🛡️ FTMO WATCHDOG: VIGILANCE ACTIVE")
    
    if not mt5.initialize():
        print("❌ MT5 Initialization Failed")
        return

    acc = mt5.account_info()
    if not acc:
        print("❌ Could not fetch account info")
        return

    initial_balance = get_initial_balance()
    daily_start_balance = acc.balance
    
    print(f"💰 Initial: ${initial_balance} | Daily Start: ${daily_start_balance}")
    telegram.send_message(f"🛡️ *WATCHDOG ACTIVE*\nMonitoring FTMO Limits...\nDaily Start: ${daily_start_balance}")

    last_heartbeat = time.time()
    
    while True:
        try:
            acc = mt5.account_info()
            if not acc:
                time.sleep(10)
                continue
            
            equity = acc.equity
            balance = acc.balance
            
            # 1. Max Total Loss Check
            total_loss = initial_balance - equity
            if total_loss >= (initial_balance * (MAX_TOTAL_LOSS_PCT / 100)):
                emergency_stop(f"Total Drawdown Limit Reached: ${total_loss:.2f}")

            # 2. Max Daily Loss Check
            daily_loss = daily_start_balance - equity
            if daily_loss >= (initial_balance * (MAX_DAILY_LOSS_PCT / 100)):
                emergency_stop(f"Daily Loss Limit Reached: ${daily_loss:.2f}")

            # 3. Daily Reset Logic
            now = datetime.now()
            # If it's 00:00 (broker time might vary, but we use system clock)
            # Simplification: if date changes, reset daily start balance
            # (In production we should use Broker Time)
            
            # Heartbeat
            if time.time() - last_heartbeat > (HEARTBEAT_MINUTES * 60):
                telegram.send_message(f"💓 *Heartbeat*: Bot is alive.\nEquity: ${equity:,.2f}\nDaily PnL: ${equity - daily_start_balance:,.2f}")
                last_heartbeat = time.time()

            # Dynamic update of display
            print(f"\r🛡️ Monitoring... Equity: ${equity:,.2f} | DD: ${daily_loss:,.2f}", end="")
            
            time.sleep(CHECK_INTERVAL_SEC)
            
        except KeyboardInterrupt:
            print("\n🛑 Watchdog stopped by user.")
            break
        except Exception as e:
            print(f"\n⚠️ Error in Watchdog loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
