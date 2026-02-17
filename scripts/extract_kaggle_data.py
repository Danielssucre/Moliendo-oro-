
import pandas as pd
import numpy as np
from pathlib import Path
import os

# Configuration
SOURCE_FILE = Path.home() / ".cache/kagglehub/datasets/anthonygocmen/multi-timeframe-fx-dataset-29-major-pairs/versions/2/TIMEFRAME_15M.csv"
OUTPUT_DIR = Path.home() / ".cache/kagglehub/datasets/anthonygocmen/multi-timeframe-fx-dataset-29-major-pairs/versions/2"
PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]

def extract_pair_data(pair, df):
    print(f"Extracting {pair}...")
    
    # Identify columns
    # Format: "Symbol", "H-Symbol", "L-Symbol", "V-Symbol"
    # Example: "EURUSD", "H-EURUSD", "L-EURUSD", "V-EURUSD"
    
    try:
        cols = {
            pair: 'close',
            f"H-{pair}": 'high',
            f"L-{pair}": 'low',
            f"V-{pair}": 'volume'
        }
        
        # Select and rename
        pair_df = df[list(cols.keys())].rename(columns=cols).copy()
        
        # Add index (Time)
        pair_df['time'] = df['time']
        
        # Synthesize Open (Open = Prev Close)
        pair_df['open'] = pair_df['close'].shift(1)
        
        # Handle first row Open (assume = Close)
        pair_df.loc[pair_df.index[0], 'open'] = pair_df.loc[pair_df.index[0], 'close']
        
        # Reorder columns: time, open, high, low, close, volume
        pair_df = pair_df[['time', 'open', 'high', 'low', 'close', 'volume']]
        
        # Save to CSV
        output_path = OUTPUT_DIR / f"{pair}_M15.csv"
        pair_df.to_csv(output_path, index=False)
        print(f"✅ Saved {output_path}")
        
    except KeyError as e:
        print(f"❌ Error extracting {pair}: Column not found {e}")

def main():
    if not SOURCE_FILE.exists():
        print(f"❌ Source file not found: {SOURCE_FILE}")
        return

    print(f"Loading {SOURCE_FILE}...")
    # Read only first few rows to check headers if needed, but here we read all
    # It's a large file, so be careful. 
    # Optimization: Read only needed columns? No, read all is easier for now.
    df = pd.read_csv(SOURCE_FILE)
    
    print(f"Loaded {len(df)} rows.")
    
    for pair in PAIRS:
        extract_pair_data(pair, df)

if __name__ == "__main__":
    main()
