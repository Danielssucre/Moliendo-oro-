import sys
import os
import json
from datetime import datetime, timedelta
import pandas as pd

# Add local paths if needed
sys.path.append(os.getcwd())

try:
    from siliconmetatrader5 import MetaTrader5
except ImportError:
    print("❌ siliconmetatrader5 library not found. Cannot connect to bridge.")
    sys.exit(1)

def load_creds():
    creds_path = "config/credentials.json"
    if os.path.exists(creds_path):
        with open(creds_path, 'r') as f:
            data = json.load(f)
            return data.get("mt5")
    return None

def check_history():
    mt5 = MetaTrader5(port=18812)
    creds = load_creds()
    
    if not creds:
        # Fallback to hardcoded ones found in run_live.py
        c_login = 1521200226
        c_pass = "Y9*VlN1c$9f*I?"
        c_server = "FTMO-Demo2"
    else:
        c_login = int(creds.get("account", 0))
        c_pass = creds.get("password", "")
        c_server = creds.get("server", "")

    print(f"📡 Connecting to MT5 Bridge on port 18812...")
    if not mt5.initialize(login=c_login, password=c_pass, server=c_server):
        print(f"❌ MT5 Initialize failed: {mt5.last_error()}")
        return

    # Set dates for today (April 13th)
    from_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    to_date = datetime.now() + timedelta(days=1)
    
    print(f"📅 Fetching history from {from_date} to {to_date}...")
    
    # Check History Deals
    deals = mt5.history_deals_get(from_date, to_date)
    
    if deals is None:
        print("No matches in history deals.")
    elif len(deals) == 0:
        print("History deals list is empty for today.")
    else:
        print(f"✅ Found {len(deals)} deals today.")
        deal_list = []
        for d in deals:
            # Manually convert properties to dict since RPyC objects might not _asdict()
            deal_list.append({
                "time": datetime.fromtimestamp(d.time).strftime('%H:%M:%S') if hasattr(d, 'time') else "?",
                "symbol": d.symbol if hasattr(d, 'symbol') else "?",
                "type": "BUY" if d.type == 0 else "SELL" if d.type == 1 else str(d.type),
                "profit": d.profit if hasattr(d, 'profit') else 0,
                "comment": d.comment if hasattr(d, 'comment') else ""
            })
        
        df = pd.DataFrame(deal_list)
        closed_deals = df[df['profit'] != 0]
        if closed_deals.empty:
            print("No realized Profit/Loss recorded today (Monday).")
        else:
            print("\n--- REALIZED TRADES TODAY ---")
            print(closed_deals.to_string(index=False))
            
    # Check Active Positions
    positions = mt5.positions_get()
    if positions:
        print(f"\n✅ {len(positions)} ACTIVE POSITIONS FOUND:")
        pos_list = []
        for p in positions:
            pos_list.append({
                "symbol": p.symbol,
                "type": "BUY" if p.type == 0 else "SELL",
                "volume": p.volume,
                "price": p.price_open,
                "profit": p.profit,
                "comment": p.comment
            })
        df_pos = pd.DataFrame(pos_list)
        print(df_pos.to_string(index=False))
    else:
        print("\nNo active positions.")

    mt5.shutdown()

if __name__ == "__main__":
    check_history()
