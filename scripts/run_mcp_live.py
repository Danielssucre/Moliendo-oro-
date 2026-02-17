import os
import sys
import time
import asyncio
from datetime import datetime
import torch
import pandas as pd
import numpy as np
from siliconmetatrader5 import MetaTrader5

# Add project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.config import config
from src.utils.logger import logger
from src.ml.execution_head import ExecutionHead
from src.ml.risk_head import RiskHead

# --- CONFIGURATION ---
MT5_PORT = 8001
TIMEFRAME = "M15" # Consistent with HIVE V5
SEQ_LEN = 20
MODEL_PATH = "data/cache/execution_head_v1.pth"

# Asset Mapping (Silicon MT5 names)
MT5_SYMBOL_MAP = {
    "EURUSD": "EURUSD",
    "GBPUSD": "GBPUSD",
    "USDJPY": "USDJPY",
    "AUDUSD": "AUDUSD",
    "USDCAD": "USDCAD",
    "NZDUSD": "NZDUSD",
    "EURGBP": "EURGBP",
    "EURJPY": "EURJPY",
    "GBPJPY": "GBPJPY",
    "AUDJPY": "AUDJPY"
}

# --- INITIALIZATION ---
mt5 = MetaTrader5(port=MT5_PORT)
if not mt5.initialize():
    logger.error(f"❌ MT5 Init Failed: {mt5.last_error()}")
    sys.exit(1)

execution_head = ExecutionHead(model_path=MODEL_PATH)
risk_head = RiskHead()

def fetch_live_data(symbol, count=150):
    """Fetches real OHLC history from MT5."""
    try:
        # TIMEFRAME translates to MT5.TIMEFRAME_M15
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, count)
        if rates is None or len(rates) == 0:
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return None

def calculate_features(df):
    """Calculates the 10 features expected by the LSTM."""
    # Matches prepare_data in train_dual_head.py
    df = df.copy()
    df['ema_9'] = df['close'].ewm(span=9).mean()
    df['ema_200'] = df['close'].ewm(span=200).mean()
    # ATR approximation: simple rolling mean of candle range
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    
    # Normalized features
    df['c_norm'] = df['close'] / df['close'].rolling(100).mean()
    df['ema9_rel'] = df['ema_9'] / df['close']
    df['ema200_rel'] = df['ema_200'] / df['close']
    df['atr_norm'] = df['atr'] / df['close']
    df['high_rel'] = df['high'] / df['close']
    df['low_rel'] = df['low'] / df['close']
    
    # Time Encoding
    df['hour'] = df['time'].dt.hour
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['day'] = df['time'].dt.dayofweek
    df['day_sin'] = np.sin(2 * np.pi * df['day'] / 7)
    df['day_cos'] = np.cos(2 * np.pi * df['day'] / 7)
    
    feature_cols = [
        'c_norm', 'ema9_rel', 'ema200_rel', 'atr_norm', 
        'high_rel', 'low_rel', 'hour_sin', 'hour_cos', 
        'day_sin', 'day_cos'
    ]
    
    # Return last sequence
    features = df[feature_cols].bfill().fillna(0).values
    if len(features) < SEQ_LEN:
        return None
    
    return torch.tensor(features[-SEQ_LEN:], dtype=torch.float32).unsqueeze(0)

def execute_live_order(symbol, direction, expectancy, sl, tp):
    """Sends a real order to MT5 with risk management."""
    # Calculate Lot Size (0.4% risk as per manual script)
    acc = mt5.account_info()
    if not acc: return
    
    risk_usd = acc.balance * 0.004
    sl_pips = abs(sl - tp) # Placeholder for lot calc, use SL dist
    # Simplified lot calculation for major pairs
    # Lot = Risk / (SL_dist * Piper_Value)
    symbol_info = mt5.symbol_info(symbol)
    if not symbol_info: return
    
    # Simplified: 0.01 for safety during initial run
    volume = 0.01 
    
    logger.info(f"🔥 EXECUTING LIVE {direction} on {symbol} | {volume} Lots")
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(volume),
        "type": mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": mt5.symbol_info_tick(symbol).ask if direction == "BUY" else mt5.symbol_info_tick(symbol).bid,
        "sl": float(sl),
        "tp": float(tp),
        "magic": 123456,
        "comment": "HIVE DualHead Live",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(f"❌ Order Failed: {result.comment}")
    else:
        logger.success(f"✅ Order Placed: #{result.order}")

async def check_for_signals():
    """Main scanning logic with live data."""
    logger.info("📡 Scanning Live MT5 Markets (HIVE V5 Dual-Head)...")
    
    # Get Real Account Info
    acc = mt5.account_info()
    if not acc:
        logger.error("❌ Could not sync account info.")
        return
    
    current_equity = acc.equity
    # Daily PnL calc (simplified: Profit field in MT5)
    daily_pnl = acc.profit 
    
    pairs = config.get_trading_config("pairs")
    
    for pair in pairs:
        try:
            mt5_symbol = MT5_SYMBOL_MAP.get(pair)
            if not mt5_symbol: continue
            
            # Fetch Live OHLC
            df = fetch_live_data(mt5_symbol)
            if df is None: continue
            
            # Extract Features
            features = calculate_features(df)
            if features is None: continue
            
            # 1. Prediction
            expectancy = execution_head.predict(features)
            direction = "BUY" if expectancy > 0 else "SELL"
            
            # 2. Risk Validation
            # Calculate mock vol_z for Bayesian Head
            vol_z = 0.5 
            
            res = risk_head.validate_signal(
                expectancy, 
                vol_z, 
                current_equity=current_equity, 
                daily_pnl=daily_pnl
            )
            
            if res["is_valid"]:
                logger.success(f"🚀 SIGNAL VALIDATED: {pair} {direction} | GT-Score: {res['gt_score']:.2f}")
                
                # Calculate SL/TP (ATR based as per HIVE V5)
                row = df.iloc[-1]
                sl_dist = row['atr'] * 1.5
                tp_dist = sl_dist * 3.0
                
                price = row['close']
                if direction == "BUY":
                    sl, tp = price - sl_dist, price + tp_dist
                else:
                    sl, tp = price + sl_dist, price - tp_dist
                
                # EXECUTE
                execute_live_order(mt5_symbol, direction, expectancy, sl, tp)
            else:
                # Optional: log heartbeat for near-hits
                if abs(expectancy) > 0.8:
                    logger.info(f"🧐 {pair}: Head 1 Expectancy={expectancy:.2f} | Head 2 VETO: {res['reason']}")
            
        except Exception as e:
            logger.error(f"❌ Error scanning {pair}: {e}")

async def main():
    while True:
        try:
            await check_for_signals()
            logger.info("💤 Sleeping for 60s...")
            await asyncio.sleep(60)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Loop error: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    print("-" * 50)
    print("🤖 HIVE DUAL-HEAD LIVE CORE ACTIVE (MT5 BRIDGE)")
    print(f"📈 Mode: PAYOFF OPTIMIZED (GMADL)")
    print(f"🛡️ Safety: FTMO COLD-BLOODED GUARD (Active)")
    print("-" * 50)
    asyncio.run(main())
    mt5.shutdown()
