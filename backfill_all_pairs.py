import sys, os
from datetime import datetime, timedelta
import json

sys.path.append(os.path.join(os.getcwd(), "src"))
from dashboard.backend.app.services.mt5_service import MT5Service
mt5 = MT5Service(os.getcwd())

HISTORY_PATH = "/Users/danielsuarezsucre/TRADING/trading_agent/config/health_history.json"

def backfill():
    if not mt5.connect():
        print("Failed to connect")
        return

    # Load existing history if any
    try:
        with open(HISTORY_PATH, "r") as f:
            history = json.load(f)
    except:
        history = {"neme1_trades": [], "neme2_trades": []}

    # Tracking tickets to avoid duplicates
    seen_tickets = {t.get("ticket") for t in history["neme1_trades"]}
    seen_tickets.update({t.get("ticket") for t in history["neme2_trades"]})

    # Scan last 60 days
    start = datetime.now() - timedelta(days=60)
    end = datetime.now() + timedelta(days=1)
    deals = mt5.client.history_deals_get(start, end)
    
    count = 0
    if deals:
        for d in deals:
            if d.profit != 0 and d.ticket not in seen_tickets:
                # We assume NEMESIS_1 unless specified in comment
                variant = "NEMESIS_1"
                if "NEMESIS_2" in str(d.comment) or "Opposite" in str(d.comment):
                    variant = "NEMESIS_2"
                
                trade_data = {
                    "profit": d.profit,
                    "is_win": d.profit > 0,
                    "symbol": d.symbol,
                    "timestamp": datetime.fromtimestamp(d.time).isoformat(),
                    "ticket": d.ticket,
                    "source": "BACKFILL_SCAN"
                }
                
                if variant == "NEMESIS_1":
                    history["neme1_trades"].append(trade_data)
                else:
                    history["neme2_trades"].append(trade_data)
                
                seen_tickets.add(d.ticket)
                count += 1

    # Save
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=4)
    
    print(f"Backfilled {count} new trades from MT5 history.")

if __name__ == "__main__":
    backfill()
