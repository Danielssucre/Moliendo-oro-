from siliconmetatrader5 import MetaTrader5
import sys

# Credentials provided by USER
LOGIN = 1512555287
PASSWORD = "VL$?5?3k582k*"
SERVER = "FTMO-Demo"

print(f"📡 Attempting to login to MT5 (Server: {SERVER}, Login: {LOGIN})...")

try:
    mt5 = MetaTrader5(port=8001)
    
    LOGIN = 1512629315
    PASSWORD = "@zn49Hw4W2*"
    SERVER = "FTMO-Demo"
    if not mt5.initialize(path='C:\\Program Files\\MetaTrader 5\\terminal64.exe', portable=True, login=LOGIN, password=PASSWORD, server=SERVER):
        print(f"❌ Initialize failed: {mt5.last_error()}")
        
        # Second attempt without portable flag
        print("Retrying without portable flag...")
        if not mt5.initialize(path='C:\\Program Files\\MetaTrader 5\\terminal64.exe', login=LOGIN, password=PASSWORD, server=SERVER):
            print(f"❌ Second Initialize failed: {mt5.last_error()}")
            sys.exit(1)
    login_result = mt5.login(login=LOGIN, password=PASSWORD, server=SERVER)
    
    if login_result:
        print("✅ SUCCESS: Logged into FTMO account!")
        
        # Verify account info
        acc = mt5.account_info()
        if acc:
            print(f"💰 Balance: {acc.balance} {acc.currency}")
            print(f"🏢 Company: {acc.company}")
            print(f"🏠 Server: {acc.server}")
        else:
            print("⚠️ Could not fetch account info after login.")
    else:
        print(f"❌ Login FAILED: {mt5.last_error()}")
        
    mt5.shutdown()

except Exception as e:
    print(f"🔥 Critical Error: {e}")
    sys.exit(1)
