#!/usr/bin/env python3
import sys
import pandas as pd
from datetime import datetime
import time

try:
    from siliconmetatrader5 import MetaTrader5
    mt5 = MetaTrader5(port=8001)
except ImportError:
    print("❌ siliconmetatrader5 library not found")
    sys.exit(1)

def main():
    print("🔍 TESTING MT5 DATA FETCHING...")
    
    if not mt5.initialize():
        print("❌ MT5 Init Failed")
        return

    print("✅ MT5 Connected")
    
    # Test Symbol
    symbol = "BTCUSD" # Try crypto first as it's active 24/7
    timeframe = mt5.TIMEFRAME_M15
    count = 100
    
    print(f"📥 Downloading last {count} M15 candles for {symbol}...")
    
    # Fetch rates
    # copy_rates_from_pos(symbol, timeframe, start_pos, count)
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    
    if rates is None or len(rates) == 0:
        print(f"❌ Failed to get data for {symbol}. Error: {mt5.last_error()}")
        
        # Try waiting for symbol to be ready
        print("⏳ Selecting symbol...")
        mt5.symbol_select(symbol, True)
        time.sleep(1)
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        
    if rates is not None and len(rates) > 0:
        print(f"✅ Received {len(rates)} records")
        
        # Debug structure
        print(f"First record type: {type(rates[0])}")
        print(f"First record: {rates[0]}")

        # Handle RPyC/Tuple structure
        # If it's a list of tuples/structs, we might need to be explicit
        data_list = []
        for r in rates:
             # Assuming standard MT5 tuple structure: (time, open, high, low, close, tick_volume, spread, real_volume)
             # But let's check what we actually get.
             # If it's a named tuple or struct from C/RPyC, maybe convert to dict or list
             data_list.append(list(r))

        # Convert to DataFrame
        df = pd.DataFrame(data_list, columns=['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume'])
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        print("\n📊 DATA PREVIEW:")
        print(df.tail())
        print("-" * 50)
        
        # Check integrity
        if df['close'].iloc[-1] > 0:
            print("✅ Data looks valid (Price > 0)")
        else:
            print("⚠️ Data looks clean/empty")
            
    else:
        print("❌ Still no data. Check if symbol exists in Market Watch.")

    mt5.shutdown()

if __name__ == "__main__":
    main()
