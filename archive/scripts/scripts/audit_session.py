#!/usr/bin/env python3
"""
NANOBOT SESSION AUDITOR
Objective: Parse logs/operations.jsonl and calculate PnL for signals generated in the last 24h.
"""
import sys
import os
import json
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LOG_FILE = "logs/operations.jsonl"

def audit_session():
    print(f"🕵️ AUDITING SESSION (Last 24h)...")
    
    if not os.path.exists(LOG_FILE):
        print("❌ No log file found.")
        return

    signals = []
    now = datetime.now()
    cutoff = now - timedelta(hours=24)
    
    with open(LOG_FILE, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line)
                # Check log timestamp
                log_ts_str = entry.get('timestamp')
                log_ts = datetime.fromisoformat(log_ts_str)
                
                if log_ts > cutoff:
                    if entry.get('type') == 'signal_generated':
                        data = entry.get('data', {})
                        # Extract Signal Details
                        signal_ts_str = data.get('timestamp') # The "Market Time"
                        pair = data.get('pair')
                        direction = data.get('direction')
                        price = data.get('entry_price')
                        tp = data.get('take_profit')
                        sl = data.get('stop_loss')
                        
                        signals.append({
                            'log_time': log_ts,
                            'signal_time': signal_ts_str,
                            'pair': pair,
                            'dir': direction,
                            'price': price,
                            'tp': tp,
                            'sl': sl
                        })
            except:
                continue
                
    if not signals:
        print("❌ No signals found in the last 24h.")
        return

    print(f"📊 Found {len(signals)} signals in logs.")
    
    # Check for Timestamp Discrepancy
    print("-" * 50)
    print(f"{'LOG TIME':<20} | {'SIGNAL TIME':<20} | {'PAIR':<8} | {'PRICE'}")
    print("-" * 50)
    
    discrepancy_count = 0
    valid_signals = []
    
    for s in signals[:5]: # Show first 5
        print(f"{str(s['log_time'])[:19]:<20} | {str(s['signal_time'])[:19]:<20} | {s['pair']:<8} | {s['price']:.4f}")
        
    for s in signals:
        # Check if signal time is roughly close to log time (within 1 day)
        # Parse signal time "YYYY-MM-DD HH:MM:SS"
        try:
            sig_dt = datetime.strptime(s['signal_time'], "%Y-%m-%d %H:%M:%S")
            diff = abs((s['log_time'] - sig_dt).total_days())
            
            if diff > 1:
                discrepancy_count += 1
            else:
                valid_signals.append(s)
        except:
            discrepancy_count += 1
            
    if discrepancy_count > len(signals) * 0.9:
        print("-" * 50)
        print(f"⚠️ MAJOR DISCREPANCY DETECTED")
        print(f"It seems {discrepancy_count} signals correspond to OLD DATES (Backtest Mode).")
        print(f"Example: Log says Today, but Signal says {signals[0]['signal_time']}")
        print("CONCLUSION: The bot was running a simulation, not live trading.")
        print("-" * 50)
        return

    # If we have valid signals, calculate PnL
    print(f"\n✅ Valid Live Signals Found: {len(valid_signals)}")
    print("Calculating Theoretical PnL...")
    
    total_pnl = 0
    wins = 0
    losses = 0
    
    for s in valid_signals:
        # Fetch OHLC data since signal
        symbol = s['pair']
        if "USD" in symbol and "X" not in symbol: symbol += "=X"
        if "BTC" in symbol: symbol = "BTC-USD"
        if "SOL" in symbol: symbol = "SOL-USD"
        
        # Determine outcome
        # (Simplified: Did it hit TP or SL?)
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d", interval="15m")
            # Filter after signal time
            sig_dt = datetime.strptime(s['signal_time'], "%Y-%m-%d %H:%M:%S")
            future = hist[hist.index.tz_localize(None) > sig_dt]
            
            outcome = "OPEN"
            pnl = 0
            
            for index, row in future.iterrows():
                high = row['High']; low = row['Low']
                
                if s['dir'] == 'BUY':
                    if low <= s['sl']: outcome = "LOSS"; pnl = -1; break
                    if high >= s['tp']: outcome = "WIN"; pnl = 2; break # Assuming 1:2 RR
                else:
                    if high >= s['sl']: outcome = "LOSS"; pnl = -1; break
                    if low <= s['tp']: outcome = "WIN"; pnl = 2; break
            
            if outcome == "WIN": wins += 1; total_pnl += pnl
            elif outcome == "LOSS": losses += 1; total_pnl += pnl
            
        except: pass
        
    print("-" * 50)
    print(f"🏆 THEORETICAL SESSION PnL")
    print("-" * 50)
    print(f"Wins: {wins}")
    print(f"Losses: {losses}")
    print(f"Net Risk Units: {total_pnl} R")
    print(f"(@ 0.2% risk/trade -> {total_pnl * 0.2:.2f}% Growth)")
    print("-" * 50)

if __name__ == "__main__":
    audit_session()
