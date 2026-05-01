
import sys
import os
from datetime import datetime, timedelta
import json

# Add local paths if needed
sys.path.append(os.getcwd())

try:
    from siliconmetatrader5 import MetaTrader5
except ImportError:
    print("❌ siliconmetatrader5 library not found.")
    sys.exit(1)

def get_detailed_comments():
    mt5 = MetaTrader5(port=18812)
    
    # Load creds from config
    try:
        with open("config/credentials.json", "r") as f:
            data = json.load(f)
            creds = data.get("mt5")
            c_login = int(creds.get("account"))
            c_pass = creds.get("password")
            c_server = creds.get("server")
    except Exception as e:
        print(f"⚠️ Error loading credentials: {e}")
        c_login = 1521200226
        c_pass = "Y9*VlN1c$9f*I?"
        c_server = "FTMO-Demo2"

    if not mt5.initialize(login=c_login, password=c_pass, server=c_server):
        print(f"❌ MT5 Initialize failed: {mt5.last_error()}")
        return

    # Set dates for Monday April 13th
    from_date = datetime(2026, 4, 13, 0, 0, 0)
    to_date = datetime(2026, 4, 14, 0, 0, 0)
    
    print(f"🔍 Mapping tickets to strategy comments for {from_date.strftime('%Y-%m-%d')}...")
    
    deals = mt5.history_deals_get(from_date, to_date)
    
    if not deals:
        print("No deals found.")
        mt5.shutdown()
        return

    # We want to map PositionID -> Entry Comment
    pos_cache = {}
    
    print(f"{'Open Time':<19} | {'Ticket':<10} | {'Symbol':<8} | {'Profit':>8} | {'Comment (Strategy)'}")
    print("-" * 80)
    
    # In the image, 'Ticket' seems to be the Position ID or the opening ticket.
    # We'll fetch the entry comment for every deal's position.
    
    results = []
    for d in deals:
        if d.entry == 1 or d.entry == 2: # OUT or INOUT (closure)
            p_id = d.position_id
            if p_id not in pos_cache:
                p_deals = mt5.history_deals_get(position=p_id)
                if p_deals:
                    entry_deal = next((pd for pd in p_deals if pd.entry == 0), None)
                    pos_cache[p_id] = entry_deal.comment if entry_deal else "Unknown"
                else:
                    pos_cache[p_id] = "Unknown"
            
            # The image shows 'Ticket' which matches either order id or position id in MT5 history
            open_time = "Unknown"
            if p_id in pos_cache:
                # Find the open time from the entry deal
                p_deals = mt5.history_deals_get(position=p_id)
                entry_deal = next((pd for pd in p_deals if pd.entry == 0), None)
                if entry_deal:
                    open_time = datetime.fromtimestamp(entry_deal.time).strftime('%Y.%m.%d %H:%M:%S')

            results.append({
                "open_time": open_time,
                "ticket": p_id, # Using position_id as it often matches the 'Ticket' in simplified reports
                "symbol": d.symbol,
                "profit": d.profit,
                "comment": pos_cache[p_id]
            })

    # Sort by time to match the image
    results.sort(key=lambda x: x['open_time'])
    
    for r in results:
        print(f"{r['open_time']:<19} | {r['ticket']:<10} | {r['symbol']:<8} | {r['profit']:>8.2f} | {r['comment']}")
            
    mt5.shutdown()

if __name__ == "__main__":
    get_detailed_comments()
