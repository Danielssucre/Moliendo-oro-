
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nanobot.utils.mt5_data import MT5DataSource
from src.nanobot.ml.stop_hunt import StopHuntModel

# --- CONFIGURATION ---
SYMBOL = "BTCUSD"
TIMEFRAME = "H1"
LOOKBACK_DAYS = 365

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("BTCUSD_FULL_BACKTEST")

def calculate_indicators(df):
    df = df.copy()
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    # ADX
    period = 14
    atr_smooth = tr.ewm(alpha=1/period, adjust=False).mean()
    up = df['high'].diff(); down = -df['low'].diff()
    plus_dm = pd.Series(0.0, index=df.index); minus_dm = pd.Series(0.0, index=df.index)
    plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
    minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    df['adx'] = dx.ewm(alpha=1/period, adjust=False).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Volatility Filter
    returns = df['close'].pct_change()
    df['vol'] = returns.rolling(24).std() * 1000
    
    return df

def run_bt():
    stop_hunt_model = StopHuntModel()
    
    with MT5DataSource() as mt5:
        if not mt5.connected: return

        logger.info(f"📊 Fetching 1 Year for {SYMBOL}...")
        end_date_abs = datetime.now()
        start_date_abs = end_date_abs - timedelta(days=LOOKBACK_DAYS + 10)
        
        all_bars = []
        current_end = end_date_abs
        while current_end > start_date_abs:
            batch_start = max(start_date_abs, current_end - timedelta(days=30))
            batch_df = mt5.get_historical_data(SYMBOL, TIMEFRAME, batch_start, current_end)
            if not batch_df.empty: all_bars.append(batch_df)
            else: break
            current_end = batch_start - timedelta(seconds=1)

        if not all_bars: return
        df = pd.concat(all_bars).drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)
        df = calculate_indicators(df)
        df = df.dropna().reset_index(drop=True)

        trades = []
        last_trade_date = None
        
        print("\n" + "="*80)
        print(f"🔬 BACKTEST INTEGRAL: {SYMBOL} (H1) - 1 AÑO")
        print("="*80)
        print(f"{'Fecha':<20} | {'Tipo':<5} | {'ADX':<5} | {'Vol':<5} | {'AI Risk':<7} | {'Resultado':<10}")
        print("-" * 80)

        for i in range(50, len(df) - 48):
            row = df.iloc[i]
            
            # 1. Signal Logic
            sig = 0
            if row['ema_9'] > row['ema_15'] and row['close'] > row['ema_200']: sig = 1
            elif row['ema_9'] < row['ema_15'] and row['close'] < row['ema_200']: sig = -1
            if sig == 0: continue
            
            # 2. Daily Limit
            current_date = row['date'].date()
            if last_trade_date == current_date: continue

            # 3. Technical Filters (15/18)
            tech_pass = (row['adx'] > 15 and row['vol'] < 18)
            
            # 4. ML Filter
            inds = {'rsi': row['rsi'], 'adx': row['adx'], 'atr': row['atr'], 'vwap': row['close']}
            features = stop_hunt_model.extract_features(df.iloc[:i+1], row['close'], inds)
            ml_risk = stop_hunt_model.predict_risk(features)
            ml_pass = (ml_risk < 0.85)

            status = "REJ-TECH" if not tech_pass else ("REJ-AI" if not ml_pass else "EXECUTED")
            
            if status != "EXECUTED":
                # Log rejected for transparency occasionally
                # print(f"{row['date']} | {status} (R={ml_risk:.2f})")
                continue

            # Simulation
            entry_price = df.iloc[i+1]['open']
            sl_dist = row['atr'] * 2.0
            tp_dist = sl_dist * 1.5
            
            sl = entry_price - sl_dist if sig == 1 else entry_price + sl_dist
            tp = entry_price + tp_dist if sig == 1 else entry_price - tp_dist
            
            outcome_r = -1.0
            found = False
            for j in range(i+1, i+48):
                f_row = df.iloc[j]
                if sig == 1:
                    if f_row['low'] <= sl: break
                    if f_row['high'] >= tp:
                        outcome_r = 1.5; found = True; break
                else:
                    if f_row['high'] >= sl: break
                    if f_row['low'] <= tp:
                        outcome_r = 1.5; found = True; break
            
            if not found:
                final_price = df.iloc[i+47]['close']
                outcome_r = ((final_price - entry_price) / sl_dist) if sig == 1 else ((entry_price - final_price) / sl_dist)

            trades.append({"symbol": SYMBOL, "date": row['date'], "type": "BUY" if sig==1 else "SELL", "r": outcome_r, "ml": ml_risk})
            last_trade_date = current_date
            print(f"{row['date']} | {'BUY' if sig==1 else 'SELL':<5} | {row['adx']:>5.1f} | {row['vol']:>5.1f} | {ml_risk:>7.2f} | {outcome_r:>10.2f}R")

        if not trades:
            print("\n❌ No trades passed all filters.")
            return

        tdf = pd.DataFrame(trades)
        win_rate = len(tdf[tdf['r'] > 0]) / len(tdf)
        total_r = tdf['r'].sum()
        avg_r = tdf['r'].mean()
        
        print("\n" + "="*80)
        print("📊 RESUMEN EJECUTIVO")
        print("-" * 80)
        print(f"Trades Totales:      {len(tdf)}")
        print(f"Win Rate:            {win_rate:.1%}")
        print(f"Expectancy:          {avg_r:.2f}R por operación")
        print(f"Rentabilidad Total:  {total_r:.2f}R")
        print(f"Max Drawdown (R):    { (tdf['r'].cumsum().cummax() - tdf['r'].cumsum()).max():.2f}R")
        print("="*80 + "\n")

if __name__ == "__main__":
    run_bt()
