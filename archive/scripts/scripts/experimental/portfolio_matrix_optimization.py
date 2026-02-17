#!/usr/bin/env python3
"""
NANOBOT SENIOR DATA SCIENTIST: PORTFOLIO MATRIX OPTIMIZATION
Objective: Quantify Marginal Contribution to Risk (MCR) and Feature Importance via Decision Trees.
"""
import sys
import os
import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.tree import DecisionTreeRegressor

# Add src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Assets
ASSETS = ["GBPUSD=X", "AUDUSD=X", "NZDUSD=X", "BTC-USD", "SOL-USD", "USDCAD=X"] # Added CAD to check if it's a better alternative? No, stick to current + maybe CAD
CURRENT_PORTFOLIO = ["GBPUSD=X", "AUDUSD=X", "NZDUSD=X", "BTC-USD", "SOL-USD"]

PERIOD = "60d"
INTERVAL = "1h"

def get_data():
    print(f"📊 FETCHING DATA FOR SENIOR ANALYSIS ({PERIOD})...")
    df = pd.DataFrame()
    for symbol in CURRENT_PORTFOLIO:
        print(f"   Downloading {symbol}...", end="\r")
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=PERIOD, interval=INTERVAL)
        if hist.empty: continue
        df[symbol] = hist['Close']
    return df.dropna()

def analyze_marginal_contribution(df):
    print("\n🧠 CALCULATING MARGINAL CONTRIBUTION TO RISK (MCR)...")
    returns = df.pct_change().dropna()
    
    # Portfolio Weights (Equal Weight Assumption for simplicity)
    weights = np.array([1/len(returns.columns)] * len(returns.columns))
    
    # Covariance Matrix
    cov_matrix = returns.cov()
    
    # Portfolio Volatility
    port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
    
    # MCR Calculation
    mcr = np.dot(cov_matrix, weights) / port_vol
    
    # Contribution to Risk %
    rc = mcr * weights
    rc_percent = rc / port_vol
    
    results = pd.DataFrame({
        "Asset": returns.columns,
        "MCR (Risk Contribution)": rc_percent * 100,
        "Individual Volatility": returns.std() * np.sqrt(24*252)
    }).sort_values(by="MCR (Risk Contribution)")
    
    print(results.round(2))
    return results

def decision_tree_importance(df):
    print("\n🌳 DECISION TREE FEATURE IMPORTANCE (Synergy Analysis)...")
    # Target: Portfolio Mean Return (Synthentic)
    # We want to see which asset PREDICTS the portfolio's success best?
    # No, we want "Uniqueness".
    
    # Let's try: Predict "GBPUSD" using "AUD, NZD, SOL, BTC".
    # If R2 is high, GBP is redundant.
    # We do this for each asset.
    
    returns = df.pct_change().dropna()
    
    uniqueness_scores = {}
    
    for target in returns.columns:
        features = returns.drop(columns=[target])
        y = returns[target]
        X = features
        
        model = RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42)
        model.fit(X, y)
        r2 = model.score(X, y)
        
        # Uniqueness = 1 - R2 (How much variance is NOT explained by others?)
        uniqueness_scores[target] = 1 - r2
        
    print("✨ UNIQUENESS SCORE (1.0 = Unique, 0.0 = Redundant):")
    res = pd.DataFrame(list(uniqueness_scores.items()), columns=["Asset", "Uniqueness"]).sort_values(by="Uniqueness", ascending=False)
    print(res.round(3))
    
    if res[res['Asset'] == 'NZDUSD=X']['Uniqueness'].values[0] < 0.2:
        print("   ⚠️ NZD IS HIGHLY REDUNDANT (Low Uniqueness).")
    else:
        print("   ✅ NZD HAS UNIQUE ALPHA (Worth Keeping).")

def run_analysis():
    df = get_data()
    analyze_marginal_contribution(df)
    decision_tree_importance(df)
    
    print("\n🎓 SENIOR SCIENTIST CONCLUSION:")
    print("   1. MCR tells us which asset adds the most RISK.")
    print("   2. Uniqueness tells us which asset adds unique ALHPA.")
    print("   If NZD has low Uniqueness AND high MCR -> KILL IT.")
    print("   If NZD has moderate Uniqueness -> KEEP IT (Diversification Benefit).")

if __name__ == "__main__":
    run_analysis()
