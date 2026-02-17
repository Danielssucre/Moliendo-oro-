from siliconmetatrader5 import MetaTrader5
import sys

print("📡 Connecting to Silicon MT5 (Manual Session)...")

try:
    # Connect to the container on port 8001
    mt5 = MetaTrader5(port=8001)
    
    # Initialize without arguments to attach to the active logged-in session
    if not mt5.initialize():
        print(f"❌ Initialize failed: {mt5.last_error()}")
        sys.exit(1)
        
    print("✅ MT5 Initialized!")
    
    # Check Version
    ver = mt5.version()
    print(f"ℹ️ Version: {ver}")
    
    # Check Account
    account = mt5.account_info()
    if account:
        print(f"🏆 Login Detected: {account.login}")
        print(f"👤 Name: {account.name}")
        print(f"💰 Balance: {account.balance} {account.currency}")
        print(f"🏢 Server: {account.server}")
        print(f"📈 Leverage: 1:{account.leverage}")
    else:
        print(f"⚠️ No account info found. Error: {mt5.last_error()}")
        
    mt5.shutdown()

except Exception as e:
    print(f"🔥 Critical Error: {e}")
    sys.exit(1)
