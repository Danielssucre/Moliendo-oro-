import rpyc
from types import SimpleNamespace
from datetime import datetime, timedelta

try:
    conn = rpyc.classic.connect("localhost", port=18812)
    remote_mt5 = conn.modules.MetaTrader5
    remote_mt5.initialize()
    
    positions_proxy = remote_mt5.positions_get()
    if positions_proxy:
        p0 = positions_proxy[0]
        print(f"Proxy found: {p0.symbol}")
        
        # Test conversion
        d = p0._asdict()
        mock = SimpleNamespace(**d)
        print(f"Mock success: {mock.symbol} | Ticket: {mock.ticket}")
        
    conn.close()
except Exception as e:
    print(f"🔥 Error: {e}")
