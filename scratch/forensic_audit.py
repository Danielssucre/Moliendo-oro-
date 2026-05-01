import json
import pandas as pd
import numpy as np
from datetime import datetime

def forensic_audit(file_path):
    print(f"--- 🕵️ FORENSIC AUDIT: {file_path} ---")
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    trades = data.get('neme1_trades', []) + data.get('neme2_trades', [])
    if not trades:
        print("No trades found.")
        return

    df = pd.DataFrame(trades)
    df['time'] = pd.to_datetime(df['time'], format='ISO8601')
    df = df.sort_values('time')
    
    # Basic Metrics
    total_trades = len(df)
    wins = df[df['profit'] > 0]
    losses = df[df['profit'] <= 0]
    
    win_rate = len(wins) / total_trades
    avg_win = wins['profit'].mean() if not wins.empty else 0
    avg_loss = abs(losses['profit'].mean()) if not losses.empty else 0
    rr_ratio = avg_win / avg_loss if avg_loss != 0 else 0
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    
    # Drawdown Analysis
    df['cumulative_profit'] = df['profit'].cumsum()
    df['peak'] = df['cumulative_profit'].cummax()
    df['drawdown'] = df['peak'] - df['cumulative_profit']
    max_dd = df['drawdown'].max()
    
    # Consecutive Losses
    df['is_loss'] = df['profit'] <= 0
    consecutive_losses = df['is_loss'].astype(int).groupby(df['is_loss'].ne(df['is_loss'].shift()).cumsum()).cumsum()
    max_consecutive_losses = consecutive_losses.max()

    # Results
    print(f"Total Transactions Audited: {total_trades}")
    print(f"Win Rate: {win_rate*100:.2f}%")
    print(f"Average Win: ${avg_win:.2f}")
    print(f"Average Loss: ${avg_loss:.2f}")
    print(f"Risk/Reward Ratio: 1:{rr_ratio:.2f}")
    print(f"Expected Payoff (Expectancy): ${expectancy:.2f}")
    print(f"Maximum Drawdown (Series): ${max_dd:.2f}")
    print(f"Max Consecutive Losses: {max_consecutive_losses}")
    
    # Autocorrelation (Lag 1)
    if total_trades > 10:
        autocorr = df['profit'].autocorr(lag=1)
        print(f"Profit Autocorrelation (Lag 1): {autocorr:.4f}")
    
    print("--- AUDIT COMPLETE ---")

if __name__ == "__main__":
    forensic_audit('/Users/danielsuarezsucre/TRADING/trading_agent/config/health_history.json')
