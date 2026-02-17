import sys
import os
import time
from siliconmetatrader5 import MetaTrader5

# --- CONFIGURATION ---
MT5_PORT = 8001
SYMBOL = "EURUSD"
VOLUME = 0.01

def test_connection():
    print(f"🚀 INITIATING MT5 CONNECTION TEST (Port: {MT5_PORT})")
    
    mt5 = MetaTrader5(port=MT5_PORT)
    if not mt5.initialize():
        print(f"❌ MT5 Init Failed: {mt5.last_error()}")
        return

    # 1. Fetch Account Info
    acc = mt5.account_info()
    if acc:
        print(f"💰 Account Sync: {acc.balance} {acc.currency} (Company: {acc.company})")
    else:
        print("❌ Could not fetch account info.")
        mt5.shutdown()
        return

    # 2. Open Test Trade
    print(f"🛒 Opening Test Trade: {SYMBOL} {VOLUME} Lots (MARKET)...")
    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        print(f"❌ Symbol {SYMBOL} not found.")
        mt5.shutdown()
        return

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": float(VOLUME),
        "type": mt5.ORDER_TYPE_BUY,
        "price": float(tick.ask),
        "magic": 999999,
        "comment": "Antigravity Connection Test",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"❌ Order Failed: {result.comment} ({result.retcode})")
    else:
        order_ticket = result.order
        print(f"✅ ORDER OPENED: #{order_ticket} at price {result.price}")
        
        # 3. Wait a moment
        print("⏳ Waiting 3 seconds before closing...")
        time.sleep(3)
        
        # 4. Close Test Trade
        print(f"🔒 Closing Test Trade #{order_ticket}...")
        tick = mt5.symbol_info_tick(SYMBOL)
        close_request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": SYMBOL,
            "volume": float(VOLUME),
            "type": mt5.ORDER_TYPE_SELL,
            "position": order_ticket,
            "price": float(tick.bid),
            "magic": 999999,
            "comment": "Antigravity Test Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        close_result = mt5.order_send(close_request)
        if close_result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"❌ Close Failed: {close_result.comment}")
        else:
            print(f"✅ ORDER CLOSED: #{close_result.order} | Result: {close_result.comment}")

    mt5.shutdown()
    print("🏁 Connection test complete.")

if __name__ == "__main__":
    test_connection()
