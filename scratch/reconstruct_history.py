
import sys
import os
import json
from datetime import datetime, timedelta

# Set up paths
PROJECT_ROOT = "/Users/danielsuarezsucre/TRADING/trading_agent"
sys.path.append(os.path.join(PROJECT_ROOT, "src"))

from siliconmetatrader5 import MetaTrader5

def normalize_symbol(s):
    if not s: return ""
    s = s.upper()
    for sx in ["USDT", "USD", "-USD", "/USD", ".P", ".m"]:
        if s.endswith(sx): s = s[:-len(sx)]
    return s

def reconstruct():
    print("🚀 Starting Magnitude-Based Statistical Reconstruction...")
    
    mt5 = MetaTrader5(port=18812)
    if not mt5.initialize():
        print("❌ FAILED to connect to MT5 Bridge. Ensure MT5 is running.")
        return

    # 1. Fetch History (90 days)
    lookback_days = 90
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)
    
    print(f"🔍 Fetching deals from {start_date.date()} to {end_date.date()}...")
    deals = mt5.history_deals_get(start_date, end_date)
    
    if not deals:
        print("⚠️ No deals found in the specified range.")
        mt5.shutdown()
        return

    print(f"✅ Found {len(deals)} total deals. Analyzing risk magnitudes...")
    
    # THRESHOLD LOGIC:
    # Account is ~$9,200.
    # Scout (B) = 0.01% risk (~$0.92)
    # Base (A) = 0.25% risk (~$23)
    # Divider = $5.00
    THRESHOLD = 5.0
    
    neme1_trades = []
    neme2_trades = []
    counts = {"A": 0, "B": 0}
    
    for d in deals:
        if d.profit == 0: continue # Skip balance operations or canceled
        
        symbol = normalize_symbol(d.symbol)
        if not symbol: continue
        
        abs_p = abs(d.profit)
        
        # Determine Variant by Magnitude
        if abs_p < THRESHOLD:
            variant = "B"
            neme2_trades.append({
                "ticket": d.ticket,
                "symbol": symbol,
                "profit": float(d.profit),
                "is_win": d.profit > 0,
                "timestamp": datetime.fromtimestamp(d.time).isoformat(),
                "source": "MAGNITUDE_RECON"
            })
            counts["B"] += 1
        else:
            variant = "A"
            neme1_trades.append({
                "ticket": d.ticket,
                "symbol": symbol,
                "profit": float(d.profit),
                "is_win": d.profit > 0,
                "timestamp": datetime.fromtimestamp(d.time).isoformat(),
                "source": "MAGNITUDE_RECON"
            })
            counts["A"] += 1

    mt5.shutdown()
    
    print(f"📊 Classification Result: A (Base)={counts['A']} | B (Scout)={counts['B']}")
    
    # 2. Save Data
    history_path = os.path.join(PROJECT_ROOT, "config/health_history.json")
    
    new_data = {
        "neme1_trades": neme1_trades,
        "neme2_trades": neme2_trades,
        "reconstructed_at": datetime.now().isoformat(),
        "reconstruction_type": "RISK_MAGNITUDE",
        "reconstruction_threshold": THRESHOLD
    }
    
    with open(history_path, "w") as f:
        json.dump(new_data, f, indent=4)
    
    print(f"✅ SUCCESS: Rebuilt history with {len(neme1_trades) + len(neme2_trades)} trades.")

if __name__ == "__main__":
    reconstruct()
