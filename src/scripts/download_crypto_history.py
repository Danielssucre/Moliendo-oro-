
import os
import sys
import pandas as pd
from datetime import datetime, timedelta
import logging

# Ensure path is reachable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.nanobot.utils.mt5_data import MT5DataSource

# --- CONFIGURATION ---
SYMBOLS = ["BTCUSD", "ETHUSD", "SOLUSD"]
TIMEFRAME = "M5"
BARS_COUNT = 100000 # ~1 year of 5M data
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/historical"))

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("CRYPTO_DOWNLOADER")

def download_symbol(symbol):
    with MT5DataSource() as ds:
        if not ds.connected:
            logger.error(f"❌ Could not connect to MT5 for {symbol}")
            return False
            
        logger.info(f"🚀 Starting deep extraction for {symbol} ({BARS_COUNT} bars, chunked)...")
        
        # Select symbol
        ds.mt5.symbol_select(symbol, True)
        
        all_rates = []
        chunk_size = 5000
        for start_pos in range(0, BARS_COUNT, chunk_size):
            logger.info(f"   -> Fetching chunk starting at {start_pos}...")
            rates = ds.mt5.copy_rates_from_pos(symbol, ds.mt5.TIMEFRAME_M5, start_pos, chunk_size)
            if rates is not None and len(rates) > 0:
                all_rates.append(pd.DataFrame(rates))
            else:
                logger.warning(f"   ⚠️ No more history found at position {start_pos}")
                break
        
        if not all_rates:
            logger.error(f"❌ Failed to fetch ANY data for {symbol}.")
            return False
            
        df = pd.concat(all_rates).drop_duplicates().sort_values('time')
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Save to CSV
        output_file = f"{OUTPUT_DIR}/MT5_5M_{symbol}_Exchange_Rate_Dataset.csv"
        df.to_csv(output_file, index=False)
        logger.info(f"✅ Saved {len(df)} total bars to {output_file}")
        return True

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for sym in SYMBOLS:
        success = download_symbol(sym)
        if not success:
            logger.warning(f"⚠️ Skipping {sym} due to error.")

if __name__ == "__main__":
    main()
