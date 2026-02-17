
import sys
import os
import time
from datetime import datetime

# Add project root to path
import site
site.addsitedir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from siliconmetatrader5 import MetaTrader5
    MT5_AVAILABLE = True
except ImportError:
    # Try adding the current directory if it's in the path
    sys.path.append(os.getcwd())
    try:
        from siliconmetatrader5 import MetaTrader5
        MT5_AVAILABLE = True
    except ImportError:
        MT5_AVAILABLE = False
        print("❌ Critical: siliconmetatrader5 library not found.")
        sys.exit(1)

def main():
    print("🔌 Connecting to MT5 Terminal (Port 8001)...")
    mt5 = MetaTrader5(port=8001)
    
    if not mt5.initialize():
        print(f"❌ Connection Failed: {mt5.last_error()}")
        return

    print(f"✅ Connected to {mt5.version()}")
    
    # 1. Account Info
    account = mt5.account_info()
    if account:
        print("\n💰 REAL ACCOUNT STATE")
        print("="*40)
        print(f"Login:       {account.login}")
        print(f"Server:      {account.server}")
        print(f"Balance:     ${account.balance:,.2f}")
        print(f"Equity:      ${account.equity:,.2f}")
        print(f"Profit:      ${account.profit:,.2f}")
        print(f"Margin:      ${account.margin:,.2f}")
        print(f"Free Margin: ${account.margin_free:,.2f}")
        print("="*40)
    else:
        print("❌ Failed to get account info")

    # 2. Open Positions
    positions = mt5.positions_get()
    
    if positions:
        print(f"\n📊 OPEN POSITIONS ({len(positions)})")
        print("-" * 100)
        print(f"{'TICKET':<10} | {'SYMBOL':<8} | {'TYPE':<4} | {'VOL':<5} | {'OPEN':<10} | {'CURRENT':<10} | {'SL':<10} | {'TP':<10} | {'PROFIT':<10}")
        print("-" * 100)
        
        total_profit = 0
        for p in positions:
            type_str = "BUY" if p.type == 0 else "SELL"
            print(f"{p.ticket:<10} | {p.symbol:<8} | {type_str:<4} | {p.volume:<5} | {p.price_open:<10.5f} | {p.price_current:<10.5f} | {p.sl:<10.5f} | {p.tp:<10.5f} | ${p.profit:<10.2f}")
            total_profit += p.profit
    else:
         print(f"\n📊 OPEN POSITIONS (0)")
         print("No open positions.")
         total_profit = 0
        
    print("-" * 100)
    print(f"TOTAL FLOATING PnL: ${total_profit:.2f}")
    print("-" * 100)

    mt5.shutdown()

if __name__ == "__main__":
    main()
