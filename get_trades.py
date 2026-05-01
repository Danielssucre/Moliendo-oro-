import sys, os
sys.path.append(os.path.join(os.getcwd(), "src"))
from dashboard.backend.app.services.mt5_service import MT5Service
from datetime import datetime, timedelta, time as dtime
import siliconmetatrader5 as mt5_client
mt5 = MT5Service(os.getcwd())
if mt5.connect():
    end = datetime.now() + timedelta(days=1)
    start = datetime.now() - timedelta(days=5)
    deals = mt5.client.history_deals_get(start, end)
    print(f"Total deals: {len(deals)}")
    
    # Let's find deals that represent position closures (profit != 0)
    closures = [d for d in deals if d.profit != 0]
    for c in closures[-20:]:  # last 20 closures
        print(f"[{datetime.fromtimestamp(c.time)}] Symbol: {c.symbol}, Profit: {c.profit}, Comment: {c.comment}, Magic: {c.magic}, Reason: {c.reason}")
