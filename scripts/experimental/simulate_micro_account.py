#!/usr/bin/env python3
"""
NANOBOT MICRO-ACCOUNT SIMULATION ($10 Challenge)
"""
import yfinance as yf
import pandas as pd
import numpy as np

PORTFOLIO = {
    "SOL-USD": "SOL-USD",
    "AUDUSD": "AUDUSD=X",
    "NZDUSD": "NZDUSD=X",
    "BTC-USD": "BTC-USD",
    "GBPUSD": "GBPUSD=X"
}
CAPITAL = 10.0
RISK_PCT = 0.002 # 0.2%
MIN_LOT_FX = 0.01
MIN_LOT_CRYPTO = 0.0001 # Binance min often $10 not units, but assumes units here

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(period).mean()

def run_simulation():
    print(f"📉 STARTING MICRO-SIMULATION")
    print(f"   Capital: ${CAPITAL}")
    print(f"   Risk: {RISK_PCT*100}% (${CAPITAL * RISK_PCT:.4f})")
    print("-" * 60)
    
    total_trades_trigger = 0
    total_trades_executed = 0
    rejected_trades = 0
    
    for name, symbol in PORTFOLIO.items():
        try:
            data = yf.download(symbol, period="30d", interval="15m", progress=False)
            if data.empty: continue
            if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0).str.lower()
            else: data.columns = data.columns.str.lower()
            
            atr = calculate_atr(data).iloc[-1]
            close = data['close'].iloc[-1]
            
            # Simulate a standard setup
            # Stop Loss = 1.5 * ATR
            sl_dist = atr * 1.5
            sl_pips = sl_dist * 10000 if "USD=X" in symbol else sl_dist
            if "JPY" in name: sl_pips = sl_dist * 100
            
            # Risk Calculation
            risk_usd = CAPITAL * RISK_PCT # $0.02
            
            # Lot Size needed
            if "USD=X" in symbol:
                # FX: Pip Value $10 per Lot
                # Risk = Lots * Sl_Pips * 10
                # Lots = Risk / (Sl_Pips * 10)
                if sl_pips > 0:
                    needed_lots = risk_usd / (sl_pips * 10.0)
                else: needed_lots = 0
                
                min_req = MIN_LOT_FX
            else:
                # Crypto: Risk = Units * Distance
                if sl_dist > 0:
                    needed_lots = risk_usd / sl_dist
                else: needed_lots = 0
                
                min_req = MIN_LOT_CRYPTO
            
            print(f"🔍 {name}:")
            print(f"   Price: {close:.4f} | ATR: {atr:.5f}")
            print(f"   SL Distance: {sl_dist:.5f} ({sl_pips:.1f} pips)")
            print(f"   Required Lots for $0.02 Risk: {needed_lots:.6f}")
            print(f"   Broker Min Lots: {min_req}")
            
            if needed_lots < min_req:
                print(f"   ❌ REJECTED: Position size too small for broker.")
                print(f"      Actual Risk if forced Min Lot: ${min_req * (sl_pips * 10 if 'USD=X' in symbol else sl_dist):.2f}")
                print(f"      (% of Account: {(min_req * (sl_pips * 10 if 'USD=X' in symbol else sl_dist) / CAPITAL * 100):.1f}%)")
                rejected_trades += 1
            else:
                print(f"   ✅ EXECUTABLE.")
                total_trades_executed += 1
                
            print("-" * 30)
            
        except Exception as e:
            print(f"Error {name}: {e}")
            
    print("\n🤖 NANOBOT REFLECTION:")
    if rejected_trades > 0:
        print("   With $10 and 0.2% risk, you simply cannot trade standard assets.")
        print("   The minimum trade size (0.01 lot) often risks $2.00 - $5.00 per trade.")
        print("   That is 20% - 50% of your entire account per trade!")
        print("   Result: You would blow the account in 1-3 losing trades.")
    else:
        print("   Miraculously possible (unlikely).")

if __name__ == "__main__":
    run_simulation()
