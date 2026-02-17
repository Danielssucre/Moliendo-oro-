#!/usr/bin/env python3
"""
NANOBOT DATA ANALYST: PORTFOLIO OPTIMIZER
Objective: specific analysis of Correlation and Sharpe Ratio to build the "Perfect Portfolio".
"""
import sys
import os
import yfinance as yf
import pandas as pd
import numpy as np
# import seaborn as sns
# import matplotlib.pyplot as plt

# current portfolio
ASSETS = ["GBPUSD=X", "AUDUSD=X", "NZDUSD=X", "BTC-USD", "SOL-USD"]
PERIOD = "60d"
INTERVAL = "1h"

def analyze_portfolio():
    print(f"📊 FETCHING DATA FOR DATA ANALYSIS ({PERIOD})...")
    
    close_prices = pd.DataFrame()
    
    for symbol in ASSETS:
        print(f"   Downloading {symbol}...", end="\r")
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=PERIOD, interval=INTERVAL)
            if hist.empty: continue
            close_prices[symbol] = hist['Close']
        except Exception as e:
            print(f"Error {symbol}: {e}")
            
    print("\n✅ Data Loaded. Computing Metrics...")
    
    # 1. Correlation Matrix
    returns = close_prices.pct_change().dropna()
    correlation = returns.corr()
    
    print("\n🔗 CORRELATION MATRIX (Redundancy Check):")
    print(correlation.round(2))
    
    # 2. Volatility & Sharpe (Simplified)
    print("\n📈 ASSET PERFORMANCE METRICS (60d):")
    summary = []
    for col in returns.columns:
        total_ret = (close_prices[col].iloc[-1] / close_prices[col].iloc[0]) - 1
        std_dev = returns[col].std() * np.sqrt(24*60) # Annualized approx
        sharpe = total_ret / std_dev if std_dev > 0 else 0
        
        summary.append({
            "Asset": col,
            "Return": total_ret * 100,
            "Volatility": std_dev,
            "Score (Sharpe)": sharpe
        })
        
    df_sum = pd.DataFrame(summary).sort_values(by="Score (Sharpe)", ascending=False)
    print(df_sum.round(2))
    
    # 3. Optimization Logic
    print("\n🧠 NANOBOT ANALYST RECOMMENDATION:")
    
    # Check AUD vs NZD
    aud_nzd_corr = correlation.loc['AUDUSD=X', 'NZDUSD=X']
    print(f"   - AUD/NZD Correlation: {aud_nzd_corr:.2f}")
    if aud_nzd_corr > 0.8:
        print("     ⚠️ HIGH CORRELATION DETECTED. You don't need both.")
        # Pick the winner
        aud_perf = df_sum[df_sum['Asset']=='AUDUSD=X']['Score (Sharpe)'].values[0]
        nzd_perf = df_sum[df_sum['Asset']=='NZDUSD=X']['Score (Sharpe)'].values[0]
        winner = "NZD" if nzd_perf > aud_perf else "AUD"
        print(f"     ✅ RECOMMENDATION: Keep {winner}, Drop the other.")
        
    # Check BTC vs SOL
    btc_sol_corr = correlation.loc['BTC-USD', 'SOL-USD']
    print(f"   - BTC/SOL Correlation: {btc_sol_corr:.2f}")
    
    if btc_sol_corr < 0.7:
        print("     ✅ Crypto Diversification looks healthy (Low Correlation). Keep both.")
    else:
        print("     ⚠️ Crypto is moving together. Consider weighting.")

if __name__ == "__main__":
    analyze_portfolio()
