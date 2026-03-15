import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from siliconmetatrader5 import MetaTrader5
    
    # Path to credentials
    creds_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "credentials.json")
    
    with open(creds_path, 'r') as f:
        config = json.load(f)
    
    account = config["mt5"]["account"]
    password = config["mt5"]["password"]
    server = config["mt5"]["server"]
    
    print(f"📡 Connecting to MT5 on port 18812...")
    mt5 = MetaTrader5(port=18812)
    
    if not mt5.initialize():
        print(f"❌ FAILED TO INITIALIZE: {mt5.last_error()}")
        sys.exit(1)
        
    print(f"🔑 Attempting login for #{account} on {server}...")
    if mt5.login(account, password, server):
        print(f"✅ LOGIN SUCCESSFUL!")
        
        acc_info = mt5.account_info()
        if acc_info:
            print(f"👤 Account Name: {acc_info.name}")
            print(f"💰 Balance: {acc_info.balance} {acc_info.currency}")
            print(f"🏢 Server: {acc_info.server}")
        
        positions = mt5.positions_get()
        print(f"📊 Active Positions: {len(positions) if positions else 0}")
        
    else:
        print(f"❌ LOGIN FAILED: {mt5.last_error()}")
        
    mt5.shutdown()
except Exception as e:
    print(f"🔥 ERROR: {e}")
