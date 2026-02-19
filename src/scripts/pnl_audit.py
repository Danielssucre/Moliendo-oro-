import sys
import os
from datetime import datetime, time as dtime
# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from siliconmetatrader5 import MetaTrader5
    mt5 = MetaTrader5(port=8001)
    if not mt5.initialize():
        print(f"FAILED TO INITIALIZE: {mt5.last_error()}")
        sys.exit(1)
        
    # Get deals for last 48 hours
    from datetime import timedelta
    start_time = datetime.now() - timedelta(hours=48)
    deals = mt5.history_deals_get(start_time, datetime.now())
    
    realized_pnl = 0
    closed_count = 0
    
    print(f"--- CLOSED TRADES TODAY ({datetime.now().date()}) ---")
    if deals:
        for d in deals:
            # We only care about deals that closed a position (entry=1 is out in some MT5 versions, but profit is the key)
            if d.profit != 0 or d.commission != 0 or d.swap != 0:
                print(f"Time: {datetime.fromtimestamp(d.time)} | Symbol: {d.symbol} | Profit: {d.profit} | Comm: {d.commission} | Swap: {d.swap}")
                realized_pnl += (d.profit + d.commission + d.swap)
                closed_count += 1
    else:
        print("No deals found for today.")
        
    print(f"\nTOTAL REALIZED PNL: {realized_pnl:.2f}")
    print(f"TOTAL CLOSED TRADES: {closed_count}")
    
    mt5.shutdown()
except Exception as e:
    print(f"ERROR: {e}")
