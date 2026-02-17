from siliconmetatrader5 import MetaTrader5
from datetime import datetime, timedelta
import time
import sys
import os

# Connect
mt5 = MetaTrader5(port=8001)
if not mt5.initialize():
    print(f"❌ Failed to connect: {mt5.last_error()}")
    sys.exit(1)

print(f"✅ Connected to {mt5.account_info().server}")
print(f"📊 Max Bars Setting: {mt5.terminal_info().maxbars}")

SYMBOLS = [
    "AUDUSD", "GBPJPY", "BTCUSD", "SOLUSD", 
    "NZDUSD", "USDCHF", "EURNZD", "GBPUSD", 
    "GBPNZD", "USDJPY", "USDCAD"
]

DAYS_TO_LOAD = 60 # Maximum days (will be clipped by 5000 bars limit)

for symbol in SYMBOLS:
    print(f"\n🚜 Processing {symbol}...")
    
    # 1. Select
    if not mt5.symbol_select(symbol, True):
        print(f"   ⚠️ Selection failed for {symbol}")
        continue
        
    # 2. Loop Days Backwards
    now = datetime.now()
    total_bars = 0
    
    for i in range(DAYS_TO_LOAD):
        date_to = now - timedelta(days=i)
        date_from = now - timedelta(days=i+1)
        
        # Request M15 Data (15)
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, date_from, date_to)
        
        count = len(rates) if rates is not None else 0
        total_bars += count
        
        print(f"   📅 {date_from.date()}: Found {count} bars")
        
        if count == 0:
            print("      ⏳ Triggering download... (Sleeping 2s)")
            time.sleep(2) # Give connection time to fetch
            
    print(f"   ✅ Total Cached: {total_bars}")

print("\n🏁 Download attempts finished.")
