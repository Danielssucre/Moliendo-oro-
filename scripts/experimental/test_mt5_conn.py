from siliconmetatrader5 import MetaTrader5
import sys

print("Testing MT5 Connection...")
mt5 = MetaTrader5(port=8001)
try:
    if mt5.initialize():
        print(f"✅ SUCCESS: Connected to MT5 v{mt5.version()}")
        mt5.shutdown()
    else:
        print(f"❌ FAILED: {mt5.last_error()}")
except Exception as e:
    print(f"⚠️ ERROR: {e}")
finally:
    sys.exit(0)
