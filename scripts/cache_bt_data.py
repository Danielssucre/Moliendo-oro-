from siliconmetatrader5 import MetaTrader5
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import pickle
import os
import sys

# MT5 Symbols (FTMO Portfolio)
MT5_SYMBOL_MAP = {
    "AUDUSD": "AUDUSD",
    "GBPJPY": "GBPJPY",
    "BTCUSD": "BTCUSD",
    "SOLUSD": "SOLUSD",
    "NZDUSD": "NZDUSD",
    "USDCHF": "USDCHF",
    "EURNZD": "EURNZD",
    "GBPUSD": "GBPUSD",
    "GBPNZD": "GBPNZD",
    "USDJPY": "USDJPY",
    "USDCAD": "USDCAD"
}

CACHE_FILE = "data/historical/bt_cache_60d.pkl"

def cache_data():
    print("⏳ Connecting to MT5 for caching...")
    mt5 = MetaTrader5(port=8001)
    if not mt5.initialize():
        print(f"❌ Failed to connect: {mt5.last_error()}")
        return

    portfolio_data = {}
    now = datetime.now()
    days_back = 60

    for pair, symbol in MT5_SYMBOL_MAP.items():
        print(f"🚜 Fetching {pair}...")
        
        if not mt5.symbol_select(symbol, True):
            print(f"   ⚠️ Symbol {symbol} not available")
            continue
            
        chunks = []
        for i in range(days_back):
            d_to = now - timedelta(days=i)
            d_from = now - timedelta(days=i+1)
            try:
                rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, d_from, d_to)
                if rates is not None and len(rates) > 0:
                    chunks.append(rates)
            except Exception: pass
            
        if not chunks:
            print(f"   ❌ No data for {pair}")
            continue
            
        # Combine and store
        all_rates = np.concatenate(chunks)
        df = pd.DataFrame(all_rates).drop_duplicates(subset=['time'])
        df = df.sort_values('time')
        # Store as dict of arrays or DF to save space/time
        portfolio_data[pair] = df
        print(f"   ✅ Cached {len(df)} bars")

    # Ensure directory exists
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    
    # Save
    with open(CACHE_FILE, 'wb') as f:
        pickle.dump(portfolio_data, f)
    
    print(f"\n✨ Cache saved to {CACHE_FILE}")
    mt5.shutdown()

if __name__ == "__main__":
    cache_data()
