import sys, os
from datetime import datetime, timedelta
sys.path.append(os.path.join(os.getcwd(), "src"))
from dashboard.backend.app.services.mt5_service import MT5Service
mt5 = MT5Service(os.getcwd())
if mt5.connect():
    start = datetime.now() - timedelta(days=30)
    end = datetime.now() + timedelta(days=1)
    deals = mt5.client.history_deals_get(start, end)
    if deals:
        import json
        history = []
        for d in deals:
            if d.symbol == "AUDNZD" and d.profit != 0:
                history.append({
                    "ticket": d.ticket,
                    "profit": d.profit,
                    "is_win": d.profit > 0,
                    "symbol": d.symbol,
                    "time": d.time,
                    "comment": d.comment
                })
        print(json.dumps(history, indent=2))
