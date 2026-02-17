from siliconmetatrader5 import MetaTrader5
import sys

# Connect
mt5 = MetaTrader5(port=8001)
if not mt5.initialize():
    print(f"❌ Init Failed: {mt5.last_error()}")
    sys.exit(1)

# Get all symbols
symbols = mt5.symbols_get()
if symbols:
    print(f"✅ Found {len(symbols)} symbols.")
    # Print the first 20 to check format
    for s in symbols[:20]:
        print(f"- {s.name}")
        
    # Check specifically for major pairs
    majors = ["EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "XAUUSD"]
    print("\n🔍 Checking Key Pairs:")
    for m in majors:
        found = any(s.name == m for s in symbols)
        if not found:
            # Try to find partial match
            partials = [s.name for s in symbols if m in s.name]
            print(f"⚠️ {m} NOT FOUND directly. Did you mean: {partials}?")
        else:
            print(f"✅ {m} verified.")
else:
    print("❌ No symbols found!")

mt5.shutdown()
