
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_deep_audit():
    try:
        from siliconmetatrader5 import MetaTrader5
        mt5 = MetaTrader5(port=8001)
        if not mt5.initialize():
            print(f"FAILED TO INITIALIZE: {mt5.last_error()}")
            return

        # Get history for the last 30 days (significant enough for FTMO evaluation)
        start_time = datetime.now() - timedelta(days=30)
        end_time = datetime.now()
        
        deals = mt5.history_deals_get(start_time, end_time)
        
        if not deals:
            print("No deals found in history.")
            return

        # Aggregate data by symbol
        stats = defaultdict(lambda: {"profit": 0, "commission": 0, "swap": 0, "total": 0, "count": 0, "losses": 0, "wins": 0})
        
        for d in deals:
            # Entry=1 (Out) means the position was closed
            if d.profit != 0 or d.commission != 0 or d.swap != 0:
                s = d.symbol
                total_pnl = d.profit + d.commission + d.swap
                
                stats[s]["profit"] += d.profit
                stats[s]["commission"] += d.commission
                stats[s]["swap"] += d.swap
                stats[s]["total"] += total_pnl
                stats[s]["count"] += 1
                
                if total_pnl < 0:
                    stats[s]["losses"] += total_pnl
                else:
                    stats[s]["wins"] += total_pnl

        # Sort by total net PnL (most negative first)
        sorted_stats = sorted(stats.items(), key=lambda x: x[1]["total"])

        print(f"--- DEEP PNL AUDIT (Last 30 Days) ---")
        print(f"{'Symbol':<10} | {'Total PnL':>12} | {'Win/Loss':^20} | {'Count'}")
        print("-" * 55)
        
        for symbol, data in sorted_stats:
            print(f"{symbol:<10} | {data['total']:>12.2f} | {data['wins']:>8.2f}/{data['losses']:<8.2f} | {data['count']}")
            
        if sorted_stats:
            worst_pair = sorted_stats[0]
            print(f"\n❌ PAIR WITH MOST LOSSES: {worst_pair[0]} (${worst_pair[1]['total']:.2f})")
        else:
            print("\nNo trades analyzed.")

        mt5.shutdown()
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    run_deep_audit()
