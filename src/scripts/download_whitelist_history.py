import os
import logging
import pandas as pd
from siliconmetatrader5 import MetaTrader5
import json

# --- CONFIG ---
BARS_COUNT = 30000
OUTPUT_DIR = "data/historical"
os.makedirs(OUTPUT_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("DataDownloader")

class MT5DataSource:
    def __init__(self):
        self.mt5 = MetaTrader5()
        self.connected = self.mt5.initialize()
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.mt5.shutdown()

def download_symbol(symbol):
    with MT5DataSource() as ds:
        if not ds.connected:
            logger.error(f"❌ Could not connect to MT5 for {symbol}")
            return False
            
        logger.info(f"🚀 Starting extraction for {symbol} ({BARS_COUNT} bars, chunked)...")
        
        # Select symbol
        ds.mt5.symbol_select(symbol, True)
        
        all_rates = []
        chunk_size = 5000
        for start_pos in range(0, BARS_COUNT, chunk_size):
            logger.info(f"   -> Fetching chunk starting at {start_pos} for {symbol}...")
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
        output_file = f"{OUTPUT_DIR}/MT5_5M_{symbol}_Training_Dataset.csv"
        df.to_csv(output_file, index=False)
        logger.info(f"✅ Saved {len(df)} total bars to {output_file}")
        return True

def main():
    # Load whitelist from config
    try:
        with open("config/trading_config.json", 'r') as f:
            cfg = json.load(f)
            whitelist = cfg.get("pairs", [])
    except Exception as e:
        logger.error(f"Could not load whitelist: {e}")
        whitelist = ["EURUSD"]

    # Add Crypto
    whitelist.extend(["BTCUSD", "ETHUSD", "SOLUSD"])
    whitelist = sorted(list(set(whitelist)))

    logger.info(f"📋 Whitelist Symbols: {whitelist}")
    
    for symbol in whitelist:
        try:
            download_symbol(symbol)
        except Exception as e:
            logger.error(f"Error downloading {symbol}: {e}")

if __name__ == "__main__":
    main()
