import os
import json
import re
import sys
from datetime import datetime, timedelta
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from siliconmetatrader5 import MetaTrader5
except ImportError:
    print("❌ siliconmetatrader5 not found")
    sys.exit(1)

# Config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "gatekeeper_config.json")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("ADAPTIVE_SENTINEL")

def get_current_threshold():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                return json.load(f).get("threshold", 0.45)
        except: pass
    return 0.45

def save_threshold(val):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump({"threshold": round(val, 3), "last_update": str(datetime.now())}, f, indent=4)
    logger.info(f"💾 Threshold updated to {val:.3f}")

def audit_performance():
    mt5 = MetaTrader5(port=8001)
    if not mt5.initialize():
        logger.error("MT5 Init Failed")
        return None

    # Find today's log
    log_name = f"trading_{datetime.now().strftime('%Y%m%d')}.log"
    log_path = os.path.join(LOGS_DIR, log_name)
    
    if not os.path.exists(log_path):
        logger.warning(f"Log not found: {log_path}")
        return None

    missed_winners = 0
    saved_losers = 0
    
    # Regex to find Gatekeeper results
    # Example: 17:47:42 | INFO     | 🛡️ GATEKEEPER: REJECT (0.35)
    # We also need the symbol and price from surrounding lines
    # Example: 17:47:42 | INFO     | 🔍 [1/5] SIGNAL FOUND: USDCAD (BUY)
    
    with open(log_path, 'r') as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        if "🛡️ GATEKEEPER: REJECT" in line:
            # Look back to find the symbol
            symbol = None
            order_type = None
            price_then = None
            
            for j in range(i-1, max(0, i-10), -1):
                prev_line = lines[j]
                match = re.search(r"SIGNAL FOUND: (\w+) \((\w+)\)", prev_line)
                if match:
                    symbol = match.group(1)
                    order_type = match.group(2)
                    # Look for Price: Price: *0.7072* or similar
                    price_match = re.search(r"Price: ([\d\.]+)", prev_line) # Simple fallback if not in log
                    break
            
            if symbol:
                # Get current price to evaluate potential
                tick = mt5.symbol_info_tick(symbol)
                if tick:
                    current_price = tick.bid if "SELL" in order_type else tick.ask
                    # We don't have the exact price then in the log line usually, 
                    # but we can get it from MT5 history at that time
                    time_str = line.split(" | ")[0]
                    # Log time is local time, usually matches MT5 if same machine
                    try:
                        ts = datetime.strptime(f"{datetime.now().strftime('%Y%m%d')} {time_str}", "%Y%m%d %H:%M:%S")
                        rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_M1, ts + timedelta(minutes=1), 1)
                        if rates is not None and len(rates) > 0:
                            price_at_signal = float(rates[0]['open'])
                            diff = current_price - price_at_signal
                            point = mt5.symbol_info(symbol).point
                            profit_pips = (diff / point) if "BUY" in order_type else (-diff / point)
                            
                            if profit_pips > 10: # Missed more than 10 pips of profit
                                missed_winners += 1
                                logger.info(f"❌ Missed Winner: {symbol} (+{profit_pips:.1f} pips)")
                            elif profit_pips < -10: # Saved more than 10 pips of loss
                                saved_losers += 1
                                logger.info(f"✅ Saved Loser: {symbol} ({profit_pips:.1f} pips)")
                    except Exception as e:
                        logger.error(f"Error evaluating {symbol}: {e}")

    mt5.shutdown()
    return missed_winners, saved_losers

def main():
    logger.info("🚀 Starting Adaptive Sentinel Audit...")
    results = audit_performance()
    if results:
        mw, sl = results
        current = get_current_threshold()
        
        # Logic: 
        # If MW > SL -> Too restrictive -> DROP threshold
        # If SL > MW -> Too risky -> RAISE threshold
        
        diff = mw - sl
        adjustment = diff * 0.02 # Small, conservative steps
        
        new_threshold = current - adjustment
        # Bounds
        new_threshold = max(0.30, min(0.65, new_threshold))
        
        if abs(new_threshold - current) > 0.001 or not os.path.exists(CONFIG_PATH):
            save_threshold(new_threshold)
        else:
            logger.info(f"⚖️ No adjustment needed. Current: {current:.3f}")

if __name__ == "__main__":
    main()
