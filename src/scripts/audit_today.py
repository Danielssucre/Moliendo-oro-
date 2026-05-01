
from siliconmetatrader5 import MetaTrader5
from datetime import datetime
import sys

def audit_today():
    mt5 = MetaTrader5(port=8001)
    if not mt5.initialize():
        print("MT5 Init Failed")
        sys.exit()

    # Define the range for Monday, April 13th, 2026
    start_date = datetime(2026, 4, 13, 0, 0, 0)
    end_date = datetime(2026, 4, 13, 23, 59, 59)
    
    deals = mt5.history_deals_get(start_date, end_date)

    print(f"\n--- TRADES FOR MONDAY, APRIL 13, 2026 ---")
    if not deals:
        print("No deals found in history for this date.")
    else:
        print(f"{'Ticket':<10} | {'Time':<19} | {'Symbol':<10} | {'Type':<5} | {'Volume':>6} | {'Profit':>10}")
        print("-" * 75)
        
        count = 0
        total_profit = 0
        for d in deals:
            # Entry=1 (OUT) or Entry=2 (INOUT) usually represents the closing deal that realizes profit
            # But in some accounts, every deal has commission/swap.
            # We filter for deals that have profit to identify closed trades, or all deals to see activity.
            if d.profit != 0 or d.entry == 1:
                t_str = datetime.fromtimestamp(d.time).strftime('%Y-%m-%d %H:%M:%S')
                d_type = "BUY" if d.type == 0 else "SELL"
                print(f"{d.ticket:<10} | {t_str:<19} | {d.symbol:<10} | {d_type:<5} | {d.volume:>6.2f} | {d.profit:>10.2f}")
                total_profit += d.profit
                count += 1
        
        print("-" * 75)
        print(f"Total Closed Trades: {count}")
        print(f"Total Day Profit: ${total_profit:.2f}")

    mt5.shutdown()

if __name__ == "__main__":
    audit_today()
