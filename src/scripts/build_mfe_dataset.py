import pandas as pd
import numpy as np
from siliconmetatrader5 import MetaTrader5
from datetime import datetime, timedelta
import os
import sys

def build_mfe_dataset():
    mt5 = MetaTrader5(port=8001)
    if not mt5.initialize():
        print("MT5 Init Failed")
        return

    # Load trades
    log_path = "data/historical/Trade_log.csv"
    if not os.path.exists(log_path):
        print(f"Log not found: {log_path}")
        return
    
    df_trades = pd.read_csv(log_path)
    print(f"Loaded {len(df_trades)} trades to process.")

    mfe_data = []

    for idx, row in df_trades.iterrows():
        symbol = row['Symbol']
        entry_time = datetime.strptime(row['Datetime'], "%Y-%m-%d %H:%M:%S")
        entry_price = row['EntryPrice']
        sl = row['SL']
        tp = row['TP']
        direction = 0 if row['Direction'] == 'BUY' else 1 # 0: BUY, 1: SELL
        
        # Risk in pips
        point = mt5.symbol_info(symbol).point
        risk_pips = abs(entry_price - sl) / point
        if risk_pips == 0: continue

        # We look for price action for the next 24 hours or until SL/TP
        # For RL training, we'll extract H1 bars
        rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_H1, entry_time + timedelta(hours=48), 50)
        if rates is None: continue
        
        rates_df = pd.DataFrame(rates)
        rates_df['time'] = pd.to_datetime(rates_df['time'], unit='s')
        rates_df = rates_df[rates_df['time'] >= entry_time].iloc[:48] # Max 48h duration

        max_r = 0
        min_r = 0
        
        for i, bar in rates_df.iterrows():
            high_pips = (bar['high'] - entry_price) / point
            low_pips = (bar['low'] - entry_price) / point
            
            if direction == 1: # SELL
                high_pips, low_pips = -low_pips, -high_pips
            
            curr_max_r = high_pips / risk_pips
            curr_min_r = low_pips / risk_pips
            
            max_r = max(max_r, curr_max_r)
            min_r = min(min_r, curr_min_r)
            
            # Feature engineering for the state
            # (In a real scenario, we'd add more technical indicators)
            mfe_data.append({
                'trade_id': idx,
                'symbol': symbol,
                'hour_of_trade': i, # Step index
                'current_r': (bar['close'] - entry_price) / (point * risk_pips) if direction == 0 else (entry_price - bar['close']) / (point * risk_pips),
                'max_r': max_r,
                'min_r': min_r,
                'volatility': (bar['high'] - bar['low']) / (entry_price * 0.001), # Normalized vol
                'direction': direction,
                'is_terminal': 1 if min_r <= -1.0 or max_r >= 3.1 else 0 # Simple termination
            })
            
            if min_r <= -1.0 or max_r >= 3.1: # Stopped out or Hit Max TP
                break

    # Save
    dataset_df = pd.DataFrame(mfe_data)
    os.makedirs("data/research", exist_ok=True)
    dataset_df.to_csv("data/research/mfe_dataset_v1.csv", index=False)
    print(f"Dataset saved to data/research/mfe_dataset_v1.csv with {len(dataset_df)} states.")
    
    mt5.shutdown()

if __name__ == "__main__":
    build_mfe_dataset()
