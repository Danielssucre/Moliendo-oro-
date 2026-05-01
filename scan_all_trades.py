import sys, os
from datetime import datetime, timedelta
sys.path.append(os.path.join(os.getcwd(), "src"))
from dashboard.backend.app.services.mt5_service import MT5Service
mt5 = MT5Service(os.getcwd())
if mt5.connect():
    start = datetime.now() - timedelta(days=60)
    end = datetime.now() + timedelta(days=1)
    deals = mt5.client.history_deals_get(start, end)
    stats = {}
    if deals:
        for d in deals:
            if d.profit != 0:
                s = d.symbol
                if s not in stats: stats[s] = {"trades": 0, "win": 0, "loss": 0, "profit": 0.0}
                stats[s]["trades"] += 1
                stats[s]["profit"] += d.profit
                if d.profit > 0: stats[s]["win"] += 1
                else: stats[s]["loss"] += 1
    
    import json
    print(json.dumps(stats, indent=2))
