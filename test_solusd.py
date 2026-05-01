import sys, os
sys.path.append(os.path.join(os.getcwd(), "src"))
from dashboard.backend.app.services.mt5_service import MT5Service
import siliconmetatrader5
mt5 = MT5Service(os.getcwd())
if mt5.connect():
    print("Testing SOLUSD tick...")
    mt5.client.symbol_select("SOLUSD", True) # Add to Market Watch just in case
    tick = mt5.client.symbol_info_tick("SOLUSD")
    print(f"tick SOLUSD: {tick}")
