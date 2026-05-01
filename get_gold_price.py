import sys, os
sys.path.append(os.path.join(os.getcwd(), "src"))
from dashboard.backend.app.services.mt5_service import MT5Service
mt5 = MT5Service(os.getcwd())
if mt5.connect():
    tick = mt5.client.symbol_info_tick("XAUUSD")
    if tick:
        print(f"XAUUSD BID: {tick.bid}, ASK: {tick.ask}")
    else:
        print("XAUUSD Tick is None")
