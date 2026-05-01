import os
import sys
import time
from dashboard.backend.app.services.mt5_service import MT5Service

# Set project root
project_root = "/Users/danielsuarezsucre/TRADING/trading_agent"
os.environ["PROJECT_ROOT"] = project_root
sys.path.append(project_root)

service = MT5Service(project_root)
print("🧐 Attempting to connect with auto-launch...")
if service.connect():
    print("✅ SUCCESS: MT5 Connected and Bridge Active!")
    info = service.client.account_info()
    print(f"Account: {info.login} | Balance: {info.balance} | Equity: {info.equity}")
else:
    print("❌ FAILED: Could not connect to MT5.")
