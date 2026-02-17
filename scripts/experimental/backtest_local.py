from siliconmetatrader5 import MetaTrader5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Import Strategy Logic
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Define Mapping Locally if import fails or for clarity
MT5_SYMBOL_MAP = {
    "AUDUSD": "AUDUSD",
    "GBPJPY": "GBPJPY",
    "BTCUSD": "BTCUSD",
    "SOLUSD": "SOLUSD",
    "NZDUSD": "NZDUSD",
    "USDCHF": "USDCHF",
    "EURNZD": "EURNZD",
    "GBPUSD": "GBPUSD",
    "GBPNZD": "GBPNZD",
    "USDJPY": "USDJPY",
    "USDCAD": "USDCAD"
}

# Config
CANDLES = 5000  # Approx 2 months of M15
TIMEFRAME = 15  # M15

def run_backtest():
    print("⏳ Connecting to Local MT5 for Backtesting...")
    # Initialize connection
    mt5 = MetaTrader5(port=8001)
    if not mt5.initialize():
        print(f"❌ Connection Failed: {mt5.last_error()}")
        return

    # Use the TIMEFRAME_M15 constant from the instance if available, else literal 15
    # The wrapper likely exposes constants via __getattr__ or similar if it proxies everything
    # Let's try to access it via mt5.TIMEFRAME_M15
    # Force constant usage or debug
    # Standard MT5 library constants:
    # M1 = 1, M5 = 5, M15 = 15, H1 = 16385, etc? 
    # No, typically M1=1, M5=5, M15=15, M30=30, H1=16385 is NOT correct.
    # Official MT5 Constants:
    # TIMEFRAME_M1=1, M2=2... M15=15, M30=30, H1=16385 (0x4001) ??
    # Actually, let's trust the instance.
    
    tf = mt5.TIMEFRAME_M15
    print(f"DEBUG: Using Timeframe Constant: {tf} (Type: {type(tf)})") 

    acc = mt5.account_info()
    server_name = acc.server if acc else "Unknown"
    print(f"✅ Connected to {server_name}")
    print(f"📜 Fetching {CANDLES} candles (M15) for Portfolio...")
    
    total_trades = 0
    total_pnl = 0.0
    wins = 0
    losses = 0
    
    # Debug: Try EURUSD explicitly first
    print("\n👉 DEBUG: Testing EURUSD M1 100 bars...")
    try:
        r = mt5.copy_rates_from_pos("EURUSD", 1, 0, 100)
        print(f"   Result: {len(r) if r is not None else 'None'}")
    except Exception as e:
        print(f"   Exception: {e}")

    for pair, symbol_mt5 in MT5_SYMBOL_MAP.items():
        # Ensure symbol is selected/subbed
        if not mt5.symbol_select(symbol_mt5, True):
            print(f"⚠️ Select Failed: {symbol_mt5}")

        # Robust Fetcher: Use Chunking (Proven in load_history.py)
        chunks = []
        now = datetime.now()
        for i in range(60):
            d_to = now - timedelta(days=i)
            d_from = now - timedelta(days=i+1)
            try:
                rates = mt5.copy_rates_range(symbol_mt5, mt5.TIMEFRAME_M15, d_from, d_to)
                if rates is not None and len(rates) > 0:
                    chunks.append(rates)
            except Exception: pass
            
        if not chunks:
            err = mt5.last_error()
            print(f"⚠️ {pair}: No Data. (Err: {err})")
            continue
            
        # Convert to DF using numpy concatenation for speed and safety
        rates_combined = np.concatenate(chunks)
        df = pd.DataFrame(rates_combined).drop_duplicates(subset=['time'])
        df = df.sort_values('time')
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        if len(df) < 200:
             print(f"⚠️ Not enough M15 bars for {pair} ({len(df)})")
             continue
        
        # Calculate Indicators (Vectorized)
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        # ATR Calculation
        high = df['high']
        low = df['low']
        close = df['close']
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()
        
        # Simulation Loop
        last_trade_day = None
        curr_pnl = 0.0
        curr_trades = 0
        curr_wins = 0
        
        # Start after 200 bars for EMA200
        for i in range(200, len(df) - 48): # Ensure room for forward look
            row = df.iloc[i]
            
            # 1. Signal Logic (HIVE V5 Trend Follow)
            sig = 0
            if row['ema_9'] > row['ema_15'] and row['close'] > row['ema_200']:
                sig = 1 # Buy State
            elif row['ema_9'] < row['ema_15'] and row['close'] < row['ema_200']:
                sig = -1 # Sell State
            
            if sig == 0: continue
            
            # 2. Daily Re-Entry Filter
            trade_day = row['time'].date()
            if trade_day == last_trade_day: continue
            
            # 3. Simulate Trade Result (1:3 Risk Reward)
            entry_price = row['close']
            atr = row['atr']
            if pd.isna(atr): continue
            
            stop_dist = atr * 1.5
            outcome = 0 # 0=Open/Neutral, 3=Win, -1=Loss
            
            # Look ahead up to 48 candles (12 hours)
            # If neither SL nor TP hit, close at end of observation (Simplified)
            # Or assume we hold until hit. Let's use 48 limit.
            
            if sig == 1:
                sl = entry_price - stop_dist
                tp = entry_price + (stop_dist * 3.0)
                
                # Check outcome candle by candle
                win = False
                loss = False
                for j in range(i+1, i+48):
                    future = df.iloc[j]
                    if future['low'] <= sl:
                        loss = True
                        break
                    if future['high'] >= tp:
                        win = True
                        break
                
                if win: outcome = 3.0
                elif loss: outcome = -1.0
                else: outcome = 0.0 # Time exit / breakeven assumption
                
            else: # Sell
                sl = entry_price + stop_dist
                tp = entry_price - (stop_dist * 3.0)
                
                win = False
                loss = False
                for j in range(i+1, i+48):
                    future = df.iloc[j]
                    if future['high'] >= sl:
                        loss = True
                        break
                    if future['low'] <= tp:
                        win = True
                        break
                        
                if win: outcome = 3.0
                elif loss: outcome = -1.0
                else: outcome = 0.0

            # Record
            last_trade_day = trade_day
            curr_trades += 1
            curr_pnl += outcome
            if outcome > 0: curr_wins += 1
        
        # Print Pair Result
        wr = (curr_wins / curr_trades * 100) if curr_trades > 0 else 0
        print(f"{pair:<8} | {curr_trades:<6} | {curr_pnl:>+8.1f} | {wr:>7.1f}%")
        
        total_trades += curr_trades
        total_pnl += curr_pnl
        wins += curr_wins
        losses += (curr_trades - curr_wins) # Includes flat 0 outcomes

    mt5.shutdown()
    
    # Final Summary
    print("-" * 40)
    print("🏁 TOTAL PORTFOLIO PERFORMANCE")
    print("-" * 40)
    print(f"Trades:  {total_trades}")
    print(f"Net PnL: {total_pnl:+.1f} R")
    
    total_wr = (wins / total_trades * 100) if total_trades > 0 else 0
    print(f"Win Rate: {total_wr:.1f}%")
    
    # Prop Firm Audit
    if total_pnl > 30: # 30R ~ 15% return approx
        print("\n✅ PROP FIRM PASS: Likely Passed")
    else:
        print("\n⚠️ PROP FIRM WARN: Optimization Needed")

if __name__ == "__main__":
    run_backtest()
