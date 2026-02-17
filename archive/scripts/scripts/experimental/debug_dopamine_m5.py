#!/usr/bin/env python3
"""
Debug script to test Dopamine Scalper M5 template directly.
"""
import sys
import os
import pandas as pd
from pathlib import Path
from datetime import datetime

# Setup project path
sys.path.append(str(Path(__file__).parent.parent))

from src.trading_agent import TradingAgent

# Load M5 data
csv_dir = Path.home() / ".cache/kagglehub/datasets/anthonygocmen/multi-timeframe-fx-dataset-29-major-pairs/versions/2"
df_5m_raw = pd.read_csv(os.path.join(csv_dir, "TIMEFRAME_5M.csv"), 
                         parse_dates=['time'], index_col='time')

# Extract EURUSD
pair = "EURUSD"
cols = [pair, f"H-{pair}", f"L-{pair}", f"V-{pair}"]
df_5m = df_5m_raw[cols].copy()
df_5m.columns = ['close', 'high', 'low', 'volume']
df_5m['open'] = df_5m['close'].shift(1).fillna(df_5m['close'])

print(f"📊 M5 Data Loaded: {len(df_5m)} candles")
print(f"   Date Range: {df_5m.index[0]} to {df_5m.index[-1]}")
print()

# Create agent
agent = TradingAgent()

# Test template on recent data
test_window = df_5m.tail(100)  # Last 100 candles
signals_found = 0

for i in range(50, len(test_window)):
    ts = test_window.index[i]
    data_slice = test_window.iloc[:i+1]
    
    data_bundle = {
        '5min': data_slice,
        '15min': data_slice,  # Dummy
        '1h': data_slice,     # Dummy
        '4h': data_slice,     # Dummy
        '1d': data_slice      # Dummy
    }
    
    cfg = {
        "strategy_template": "dopamine_m5_scalper"
    }
    
    try:
        signal = agent._get_primitive_signal(pair, data_bundle, ts, cfg)
        if signal:
            signals_found += 1
            print(f"✅ SIGNAL FOUND at {ts}: {signal['direction'].upper()}")
            print(f"   Entry Price: {signal['entry_price']:.5f}")
            print(f"   Hour UTC: {ts.hour}")
            print()
    except Exception as e:
        print(f"❌ ERROR at {ts}: {e}")
        import traceback
        traceback.print_exc()
        break

print(f"\n📊 SUMMARY:")
print(f"   Candles Tested: {len(test_window) - 50}")
print(f"   Signals Found: {signals_found}")
print(f"   Signal Rate: {signals_found / (len(test_window) - 50) * 100:.1f}%")

if signals_found == 0:
    print("\n⚠️  NO SIGNALS FOUND - Debugging:")
    
    # Check session hours
    print("\n1. Session Hours Distribution:")
    hour_counts = test_window.index.hour.value_counts().sort_index()
    print(f"   Total candles by hour (UTC):")
    for hour, count in hour_counts.items():
        in_session = (0 <= hour <= 3) or (10 <= hour <= 14)
        marker = "✅" if in_session else "  "
        print(f"   {marker} {hour:02d}:00 - {count} candles")
    
    # Check EMA crossovers
    print("\n2. EMA Analysis (last 10 candles):")
    ema5 = test_window['close'].ewm(span=5).mean()
    ema13 = test_window['close'].ewm(span=13).mean()
    for i in range(-10, 0):
        cross_up = ema5.iloc[i] > ema13.iloc[i] and ema5.iloc[i-1] <= ema13.iloc[i-1]
        cross_down = ema5.iloc[i] < ema13.iloc[i] and ema5.iloc[i-1] >= ema13.iloc[i-1]
        marker = "🔼" if cross_up else ("🔽" if cross_down else "  ")
        print(f"   {marker} {test_window.index[i]}: EMA5={ema5.iloc[i]:.5f}, EMA13={ema13.iloc[i]:.5f}")
