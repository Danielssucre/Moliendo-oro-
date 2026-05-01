
import sys
import os
import logging
import json
from datetime import datetime, timedelta

# Path resolution
current_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(current_dir))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, SRC_DIR)

from nanobot.state_persistence import StatePersistence
from siliconmetatrader5 import MetaTrader5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ForensicHarvester")

def run_forensic_harvest():
    mt5 = MetaTrader5(port=18812)
    if not mt5.initialize():
        logger.error("Failed to initialize MT5")
        return

    persistence = StatePersistence()
    
    # Scan last 14 days of history to have more data
    now = datetime.now()
    from_date = now - timedelta(days=14)
    
    logger.info(f"🔍 Starting Forensic Harvest from {from_date}...")
    
    deals = mt5.history_deals_get(from_date, now + timedelta(hours=1))
    if not deals:
        logger.warning("No deals found in the specified range.")
        return

    # Group deals by position ID
    pos_history = {}
    for d in deals:
        if d.position_id not in pos_history:
            pos_history[d.position_id] = []
        pos_history[d.position_id].append(d)

    # Filter deals by comment (MEGA_V2)
    grid_data = {} 
    
    for pid, history in pos_history.items():
        for d in history:
            comment = getattr(d, 'comment', '')
            if "_L" in comment and "MEGA" in comment:
                symbol = d.symbol
                if symbol not in grid_data: grid_data[symbol] = {}
                
                # Group by 4-hour window to approximate a basket
                basket_time_key = d.time // 14400 
                if basket_time_key not in grid_data[symbol]:
                    grid_data[symbol][basket_time_key] = {"levels": [], "l1": None}
                
                try:
                    # Extract level from comment like ..._L1_...
                    level_part = [s for s in comment.split('_') if s.startswith('L') and s[1:].isdigit()]
                    if level_part:
                        level = int(level_part[0][1:])
                        if level == 1:
                            grid_data[symbol][basket_time_key]["l1"] = d.price
                        grid_data[symbol][basket_time_key]["levels"].append({"level": level, "price": d.price})
                except: continue

    # Process extracted baskets
    harvested_count = 0
    import pandas as pd
    import numpy as np

    for symbol, baskets in grid_data.items():
        # Get ATR for symbol
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 20)
        if rates is None or len(rates) < 14: continue
        
        df = pd.DataFrame(rates)
        tr = pd.concat([df['high']-df['low'], abs(df['high']-df['close'].shift(1)), abs(df['low']-df['close'].shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        
        if not atr or atr <= 0: continue

        for b_key, data in baskets.items():
            if data["l1"] and data["levels"]:
                # Pivot = highest level reached
                max_level_data = max(data["levels"], key=lambda x: x["level"])
                max_level = max_level_data["level"]
                
                # Distance in ATR from L1 to the Pivot
                dist_price = abs(max_level_data["price"] - data["l1"])
                dist_atr = dist_price / atr
                
                if dist_atr > 0:
                    logger.info(f"📈 [FORENSIC] {symbol}: Reversal at L{max_level} ({dist_atr:.2f} ATR)")
                    persistence.update_reversal_profile(symbol, dist_atr)
                    harvested_count += 1

    logger.info(f"✅ Forensic Harvest Complete. {harvested_count} data points added to reversal_profile.")
    mt5.shutdown()

if __name__ == "__main__":
    run_forensic_harvest()
