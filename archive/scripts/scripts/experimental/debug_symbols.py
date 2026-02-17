import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from siliconmetatrader5 import MetaTrader5
    mt5 = MetaTrader5(port=8001)
    if mt5.initialize():
        print(f"✅ Connected to MT5")
        positions = mt5.positions_get()
        if positions:
            print(f"--- ACTIVE POSITIONS ({len(positions)}) ---")
            for p in positions:
                print(f"Symbol: {p.symbol}, Type: {p.type}, Ticket: {p.ticket}")
        else:
            print("No active positions.")
            
        orders = mt5.orders_get()
        if orders:
            print(f"--- ACTIVE ORDERS ({len(orders)}) ---")
            for o in orders:
                print(f"Symbol: {o.symbol}, Type: {o.type}, Ticket: {o.ticket}")
        else:
            print("No active orders.")
            
        # Check ASSET_MAP symbols exist
        ASSETS = ["AUDUSD", "GBPJPY", "BTCUSD", "NZDUSD", "USDCHF", "EURNZD", "GBPUSD", "GBPNZD", "USDJPY", "USDCAD"]
        print("--- SYMBOL VALIDATION ---")
        for s in ASSETS:
            selected = mt5.symbol_select(s, True)
            print(f"Asset: {s}, Exists: {selected}")
    else:
        print("❌ MT5 Init failed")
except Exception as e:
    print(f"⚠️ Error: {e}")
