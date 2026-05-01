import json
import pandas as pd
import numpy as np
from datetime import datetime

def analyze_phase_1():
    try:
        with open('logs/history/master_ledger.json', 'r') as f:
            trades = json.load(f)
    except Exception as e:
        print(f"Error loading master_ledger: {e}")
        return

    df = pd.DataFrame(trades)
    if df.empty:
        print("No trades found in master_ledger.")
        return

    # Filter for closed trades (usually identified by profit/loss)
    # MT5 commission and swap should be included for net payoff
    df['net_profit'] = df['profit'] + df.get('commission', 0) + df.get('swap', 0)
    
    total_trades = len(df)
    wins = df[df['net_profit'] > 0]
    losses = df[df['net_profit'] <= 0]
    
    win_rate = len(wins) / total_trades
    avg_win = wins['net_profit'].mean()
    avg_loss = abs(losses['net_profit'].mean())
    rr_ratio = avg_win / avg_loss if avg_loss != 0 else 0
    expected_payoff = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    
    print(f"--- FASE 1: MÉTRICAS ESTADÍSTICAS ---")
    print(f"Muestra total: {total_trades} operaciones")
    print(f"Win Rate: {win_rate:.2%}")
    print(f"Average Win: ${avg_win:.2f}")
    print(f"Average Loss: ${avg_loss:.2f}")
    print(f"Risk/Reward Ratio (Real): {rr_ratio:.2f}:1")
    print(f"Expected Payoff: ${expected_payoff:.2f} por trade")

    # Drawdown Analysis from Equity Timeseries
    try:
        equity_df = pd.read_json('config/equity_timeseries.jsonl', lines=True)
        if not equity_df.empty:
            equity_df['peak'] = equity_df['equity'].cummax()
            equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak'])
            equity_df['drawdown_pct'] = (equity_df['drawdown'] / equity_df['peak']) * 100
            
            max_dd_abs = abs(equity_df['drawdown'].min())
            max_dd_pct = abs(equity_df['drawdown_pct'].min())
            
            print(f"\n--- FASE 1: PERFIL DE RIESGO ---")
            print(f"Max Drawdown (Absoluto): ${max_dd_abs:.2f}")
            print(f"Max Drawdown (%): {max_dd_pct:.2f}%")
    except Exception as e:
        print(f"Error analyzing equity drawdown: {e}")

    # Temporal Dependency (Autocorrelation)
    # Simplifying: Checking if win follows win
    df['is_win'] = df['net_profit'] > 0
    df['prev_win'] = df['is_win'].shift(1)
    
    win_after_win = df[(df['is_win'] == True) & (df['prev_win'] == True)]
    total_wins = df[df['is_win'] == True]
    
    p_win_after_win = len(win_after_win) / (len(total_wins) - 1) if len(total_wins) > 1 else 0
    
    print(f"\n--- FASE 1: DEPENDENCIAS TEMPORALES ---")
    print(f"Prob. Win after Win: {p_win_after_win:.2%}")
    print(f"Baseline Win Rate: {win_rate:.2%}")
    if abs(p_win_after_win - win_rate) > 0.05:
        print("Aviso: Se observa una ligera autocorrelación (Cluster de rachas).")
    else:
        print("Los eventos parecen ser estadísticamente independientes (no hay clusterización significativa).")

if __name__ == "__main__":
    analyze_phase_1()
