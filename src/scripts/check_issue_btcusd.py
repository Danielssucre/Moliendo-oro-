from siliconmetatrader5 import MetaTrader5
from datetime import datetime
import sys

mt5 = MetaTrader5(port=8001)
if not mt5.initialize():
    print("MT5 Init Failed")
    sys.exit()

ticket = 388934654
positions = mt5.positions_get(ticket=ticket)

if positions:
    pos = positions[0]
    # Time in MT5 is seconds since 1970
    open_time = datetime.fromtimestamp(pos.time)
    now = datetime.now()
    duration_hours = (now - open_time).total_seconds() / 3600
    
    print(f"SYMBOL: {pos.symbol}")
    print(f"TICKET: {pos.ticket}")
    print(f"OPEN TIME: {open_time}")
    print(f"DURATION: {duration_hours:.2f} hours")
    print(f"OPEN PRICE: {pos.price_open}")
    print(f"CURRENT PRICE: {pos.price_current}")
    print(f"SL: {pos.sl}")
    print(f"TP: {pos.tp}")
    print(f"PROFIT: {pos.profit}")
else:
    print(f"Position {ticket} not found (likely closed).")

mt5.shutdown()
