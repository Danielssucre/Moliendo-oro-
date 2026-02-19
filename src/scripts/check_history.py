from siliconmetatrader5 import MetaTrader5
from datetime import datetime, timedelta
import sys

mt5 = MetaTrader5(port=8001)
if not mt5.initialize():
    print("MT5 Init Failed")
    sys.exit()

# Get deals for last 6 hours
start_time = datetime.now() - timedelta(hours=6)
deals = mt5.history_deals_get(start_time, datetime.now())

print(f"--- RECENT CLOSED TRADES (Last 6h) ---")
if deals:
    for d in deals:
        if d.profit != 0:
            print(f"Time: {datetime.fromtimestamp(d.time)} | Symbol: {d.symbol} | Profit: {d.profit} | Type: {'Buy' if d.type==0 else 'Sell'}")
else:
    print("No closed trades in the last 6 hours.")

mt5.shutdown()
