from siliconmetatrader5 import MetaTrader5
import datetime

def run():
    print("⏳ Connecting to MT5...")
    mt5 = MetaTrader5(port=8001)
    if not mt5.initialize():
        print(f"❌ Init Failed: {mt5.last_error()}")
        return

    print(f"✅ Version: {mt5.version()}")
    print(f"✅ Terminal Info: {mt5.terminal_info()}")
    
    symbol = "EURUSD"
    print(f"👉 Selecting {symbol}...")
    sel = mt5.symbol_select(symbol, True)
    print(f"   Result: {sel}")
    
    print("\n👉 Testing copy_rates_from_pos(EURUSD, 1, 0, 10)...")
    try:
        rates = mt5.copy_rates_from_pos(symbol, 1, 0, 10)
        print(f"   Rates: {rates}")
        if rates is None: print(f"   Error: {mt5.last_error()}")
    except Exception as e:
        print(f"   Exception: {e}")

if __name__ == "__main__":
    run()
