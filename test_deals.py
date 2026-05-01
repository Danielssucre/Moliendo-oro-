import sys, os
sys.path.append(os.path.join(os.getcwd(), "src"))
from dashboard.backend.app.services.mt5_service import MT5Service
from datetime import datetime, timedelta
import siliconmetatrader5 as mt5_client
mt5 = MT5Service(os.getcwd())
if mt5.connect():
    start = datetime.now() - timedelta(days=365)
    end = datetime.now()
    end_plus_1 = datetime.now() + timedelta(days=1)
    
    deals1 = mt5.client.history_deals_get(start, end)
    deals2 = mt5.client.history_deals_get(start, end_plus_1)
    print("Deals (end=now):", len(deals1) if deals1 else 0)
    print("Deals (end=now+1d):", len(deals2) if deals2 else 0)
