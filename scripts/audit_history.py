import sys
import os
from datetime import datetime, timedelta
import pandas as pd

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from siliconmetatrader5 import MetaTrader5
    mt5 = MetaTrader5(port=8001)
except ImportError:
    print("Error: siliconmetatrader5 not found.")
    sys.exit(1)

def audit_today():
    if not mt5.initialize():
        print("MT5 Init Failed")
        return

    # Fetch deals from today
    from_date = datetime.now().replace(hour=0, minute=0, second=0)
    to_date = datetime.now()
    
    deals = mt5.history_deals_get(from_date, to_date)
    
    if deals is None:
        print("No deals found today.")
        return

    print(f"\n📊 AUDITORÍA DE TRADES - {from_date.strftime('%Y-%m-%d')} 🛡️")
    print("-" * 60)
    
    total_pnl = 0
    trades_list = []
    
    for d in deals:
        # 1 = Deal Entry, 2 = Deal Exit (approx in silicon mt5)
        # Actually fields might vary, let's look at the object
        pnl = d.profit + d.commission + d.swap
        total_pnl += pnl
        
        trades_list.append({
            'Time': datetime.fromtimestamp(d.time).strftime('%H:%M:%S'),
            'Symbol': d.symbol,
            'Type': "BUY" if d.type == 0 else "SELL",
            'Volume': d.volume,
            'Price': d.price,
            'PnL': pnl,
            'Comment': d.comment
        })

    df = pd.DataFrame(trades_list)
    print(df.to_string())
    print("-" * 60)
    print(f"💰 PnL TOTAL HOY: ${total_pnl:.2f}")

    # Check for BTCUSD concentration
    btc_trades = df[df['Symbol'] == 'BTCUSD']
    if not btc_trades.empty:
        print(f"🚨 CONCENTRACIÓN BTCUSD: {len(btc_trades)} operaciones detectadas.")

if __name__ == "__main__":
    audit_today()
