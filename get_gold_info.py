import sys, os
sys.path.append(os.path.join(os.getcwd(), "src"))
from dashboard.backend.app.services.mt5_service import MT5Service
mt5 = MT5Service(os.getcwd())
if mt5.connect():
    info = mt5.client.symbol_info("XAUUSD")
    tick = mt5.client.symbol_info_tick("XAUUSD")
    if tick and info:
        print(f"XAUUSD BID: {tick.bid}, ASK: {tick.ask}")
        print(f"Point: {info.point}, TickSize: {info.trade_tick_size}, TickValue: {info.trade_tick_value}")
    else:
        print("XAUUSD info/tick is None")
