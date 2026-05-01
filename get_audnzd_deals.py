import sys, os
from datetime import datetime, timedelta
sys.path.append(os.path.join(os.getcwd(), "src"))
from dashboard.backend.app.services.mt5_service import MT5Service
mt5 = MT5Service(os.getcwd())
if mt5.connect():
    start = datetime.now() - timedelta(days=30)
    end = datetime.now() + timedelta(days=1)
    deals = mt5.client.history_deals_get(start, end)
    count = 0
    if deals:
        for d in deals:
            if d.symbol == "AUDNZD" and d.profit != 0:
                print(f"Deal {d.ticket}: Profit {d.profit}, Comment: {d.comment}, Magic: {d.magic}")
                count += 1
    print(f"Total AUDNZD closing deals: {count}")
