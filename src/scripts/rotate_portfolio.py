import os
import json
import sys
import pandas as pd
import numpy as np
from datetime import datetime
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from siliconmetatrader5 import MetaTrader5
except ImportError:
    print("❌ siliconmetatrader5 not found")
    sys.exit(1)

# Config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PORTFOLIO_CONFIG = os.path.join(BASE_DIR, "config", "portfolio.json")

CANDIDATES = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCAD", "USDCHF", "AUDUSD", "NZDUSD",
    "EURJPY", "GBPJPY", "AUDJPY", "EURNZD", "EURAUD", "GBPAUD",
    "BTCUSD", "ETHUSD", "SOLUSD", "XAUUSD"
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("PORTFOLIO_ROTATOR")

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(period).mean()

def calculate_adx(df, period=14):
    high = df['high']; low = df['low']; close = df['close']
    tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr_smooth = tr.ewm(alpha=1/period, adjust=False).mean()
    up = high.diff(); down = -low.diff()
    plus_dm = pd.Series(0.0, index=df.index); minus_dm = pd.Series(0.0, index=df.index)
    plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
    minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    return dx.ewm(alpha=1/period, adjust=False).mean()

def get_trend_score(mt5, symbol):
    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 250)
        if rates is None or len(rates) < 200:
            return 0
            
        df = pd.DataFrame(rates)
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        df['adx'] = calculate_adx(df)
        
        last = df.iloc[-1]
        
        # Trend Alignment Bonus
        bulk_trend = 1.0
        if last['close'] > last['ema_200'] and last['ema_9'] > last['ema_15']:
            bulk_trend = 1.5 # Strong Buy Trend
        elif last['close'] < last['ema_200'] and last['ema_9'] < last['ema_15']:
            bulk_trend = 1.5 # Strong Sell Trend
        else:
            bulk_trend = 0.5 # Ranging
            
        # Overall Score = ADX * Alignment
        score = last['adx'] * bulk_trend
        return score
    except:
        return 0

def main():
    mt5 = MetaTrader5(port=8001)
    if not mt5.initialize():
        logger.error("MT5 Init Failed")
        return

    scores = {}
    logger.info(f"🔍 Scanning {len(CANDIDATES)} candidates for HIVE Alpha...")
    
    for symbol in CANDIDATES:
        info = mt5.symbol_info(symbol)
        if not info: continue
        
        score = get_trend_score(mt5, symbol)
        scores[symbol] = score
        logger.info(f"Symbol: {symbol:<8} | Score: {score:.1f}")

    # Top 4
    sorted_pairs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_4 = sorted_pairs[:4]
    
    new_assets = {pair: pair for pair, score in top_4}
    
    logger.info(f"🏆 TOP 4 SELECTED: {list(new_assets.keys())}")
    
    # Save
    os.makedirs(os.path.dirname(PORTFOLIO_CONFIG), exist_ok=True)
    with open(PORTFOLIO_CONFIG, 'w') as f:
        json.dump({"assets": new_assets, "updated_at": str(datetime.now())}, f, indent=4)
    
    mt5.shutdown()

if __name__ == "__main__":
    main()
