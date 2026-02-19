import sys
import os
# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from siliconmetatrader5 import MetaTrader5
    mt5 = MetaTrader5(port=8001)
    if not mt5.initialize():
        print(f"FAILED TO INITIALIZE: {mt5.last_error()}")
        sys.exit(1)
        
    positions = mt5.positions_get()
    orders = mt5.orders_get()
    
    print("--- POSITIONS (ACTIVE TRADES) ---")
    if positions:
        for p in positions:
            print(f"Ticket: {p.ticket} | Symbol: {p.symbol} | Type: {p.type} | Profit: {p.profit}")
    else:
        print("No active positions.")
        
    print("\n--- PENDING ORDERS ---")
    if orders:
        for o in orders:
            print(f"Ticket: {o.ticket} | Symbol: {o.symbol} | Type: {o.type} | Price: {o.price_open} | Comment: {o.comment}")
    else:
        print("No pending orders.")
        
    mt5.shutdown()
except Exception as e:
    print(f"ERROR: {e}")
