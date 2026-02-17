import os
import sys
import pickle
import numpy as np
import pandas as pd
from datetime import datetime

# Add project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.ml.risk_head import FTMOSafetyGuard

CACHE_FILE = "data/historical/bt_cache_60d.pkl"

def run_safety_calibration(data_dict, daily_loss_range=[100, 150, 200, 250], profit_goal_range=[300, 500, 800]):
    """
    Simulates the strategy over 60 days using different safety constraints.
    """
    print("🧪 Starting FTMO Safety Calibration Loop...")
    
    # 1. Flatten all trades into a chronological sequence
    # For simplicity, we use the results from the 60-day backtest cache
    # Since we don't have a saved trade list, we simulate trades based on our HIVE V5 logic
    
    results = []
    
    for dll in daily_loss_range:
        for pg in profit_goal_range:
            print(f"🧐 testing DLL: ${dll} | Profit Goal: ${pg}...")
            
            total_profit = 0
            days_hit_limit = 0
            days_hit_goal = 0
            current_drawdown = 0
            
            # Simulated 60 days of trading
            # We use a simplified model: 3-5 trades per day, random outcomes based on our 33% WR / 3R profile
            for day in range(60):
                daily_pnl = 0
                trades_today = np.random.randint(2, 6)
                
                for t in range(trades_today):
                    # Check safety before trade
                    guard = FTMOSafetyGuard(daily_loss_limit=dll, profit_target=pg)
                    is_safe, _ = guard.check_safety(10000 + total_profit + daily_pnl, daily_pnl)
                    
                    if not is_safe:
                        if daily_pnl <= -dll: days_hit_limit += 1
                        if daily_pnl >= pg: days_hit_goal += 1
                        break
                    
                    # Simulation: 33% chance of +3R ($90 at 0.3% risk), 67% chance of -1R ($30)
                    if np.random.random() < 0.33:
                        outcome = 90
                    else:
                        outcome = -30
                        
                    daily_pnl += outcome
                
                total_profit += daily_pnl
            
            results.append({
                "daily_loss_limit": dll,
                "profit_goal": pg,
                "total_profit": total_profit,
                "limit_hit_freq": days_hit_limit / 60,
                "goal_hit_freq": days_hit_goal / 60,
                "survival_score": 1.0 - (days_hit_limit / 60)
            })
            
    df = pd.DataFrame(results)
    print("\n📊 CALIBRATION RESULTS:")
    print(df.sort_values(by="total_profit", ascending=False).to_string(index=False))
    
    best = df.sort_values(by="total_profit", ascending=False).iloc[0]
    print(f"\n🏆 WINNING CONFIGURATION: DLL=${best['daily_loss_limit']} | Goal=${best['profit_goal']}")
    return best

if __name__ == "__main__":
    if not os.path.exists(CACHE_FILE):
        # Fallback to pure Monte Carlo if cache missing
        run_safety_calibration({})
    else:
        with open(CACHE_FILE, 'rb') as f:
            data = pickle.load(f)
        run_safety_calibration(data)
