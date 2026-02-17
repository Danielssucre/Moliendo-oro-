#!/usr/bin/env python3
"""
Yearly Backtest Simulation - $100 Capital (Nanobot V1.2 RL-Runner)
Tests the RL policy over 1 year with a $100 starting balance and 0.01 lot floor.
Uses batch data fetching for robustness.
"""
import sys
import os
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from datetime import datetime, timedelta
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nanobot.utils import MT5DataSource
from src.nanobot.rl_manager import RLTrailingManager

# --- CONFIGURATION ---
SYMBOLS = ["AUDUSD", "GBPJPY", "BTCUSD", "NZDUSD", "USDCHF", "EURNZD", "GBPUSD", "GBPNZD", "USDJPY", "USDCAD"]
TIMEFRAME = "H1"
LOOKBACK_DAYS = 365
STARTING_CAPITAL = 100.0
RISK_PER_TRADE_TARGET = 0.004 # 0.4% Target
LOT_FLOOR = 0.01

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("BT_100USD")

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
    high = df['high']; low = df['low']; close = df['close']
    tr_adx = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr_smooth = tr_adx.ewm(alpha=1/period, adjust=False).mean()
    up = high.diff(); down = -low.diff()
    plus_dm = pd.Series(0.0, index=df.index); minus_dm = pd.Series(0.0, index=df.index)
    plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
    minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / (atr_smooth + 1e-9))
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / (atr_smooth + 1e-9))
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
    df['adx'] = dx.ewm(alpha=1/period, adjust=False).mean()
    
    # Volatility
    returns = df['close'].pct_change()
    df['vol'] = returns.rolling(24).std() * 1000
    
    return df

def run_backtest():
    logger.info(f"🚀 Starting 1-Year Backtest with ${STARTING_CAPITAL} Capital...")
    
    rl_manager = RLTrailingManager(model_path="models/infinite_rl_qnet_v1.pth")
    if not rl_manager.enabled:
        logger.error("RL Manager not enabled. Check model path.")
        return

    all_trades = []
    
    with MT5DataSource() as mt5:
        if not mt5.connected:
            logger.error("MT5 Connection Failed")
            return
            
        for symbol in SYMBOLS:
            logger.info(f"📊 Processing {symbol}...")
            
            end_date_abs = datetime.now()
            start_date_abs = end_date_abs - timedelta(days=LOOKBACK_DAYS + 30)
            
            all_bars = []
            curr_end = end_date_abs
            
            while curr_end > start_date_abs:
                batch_start = max(start_date_abs, curr_end - timedelta(days=30))
                batch_df = mt5.get_historical_data(symbol, TIMEFRAME, batch_start, curr_end)
                
                if not batch_df.empty:
                    all_bars.append(batch_df)
                else:
                    if len(all_bars) > 0: break 
                
                curr_end = batch_start - timedelta(seconds=1)

            if not all_bars:
                logger.warning(f"❌ No data found for {symbol}")
                continue
            
            df = pd.concat(all_bars).drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)
            df = calculate_indicators(df)
            test_start = end_date_abs - timedelta(days=LOOKBACK_DAYS)
            test_df = df[df['date'] >= test_start].copy().reset_index(drop=True)
            
            if test_df.empty: continue
            
            last_trade_date = None
            
            for i in range(len(test_df) - 1):
                row = test_df.iloc[i]
                
                # Signal logic HIVE V5
                sig = 0
                if row['ema_9'] > row['ema_15'] and row['close'] > row['ema_200']:
                    sig = 1
                elif row['ema_9'] < row['ema_15'] and row['close'] < row['ema_200']:
                    sig = -1
                
                if sig == 0: continue
                current_date = row['date'].date()
                if last_trade_date == current_date: continue
                if not (row['adx'] > 15 and row['vol'] < 18): continue
                
                # Trade Setup
                entry_price = test_df.iloc[i+1]['open']
                entry_time = test_df.iloc[i+1]['date']
                atr_val = row['atr']
                sl_dist = atr_val * 2.0
                
                # Pip Calculation
                pip_val = 0.0001
                if "JPY" in symbol: pip_val = 0.01
                if "BTC" in symbol: pip_val = 1.0
                risk_pips = sl_dist / pip_val
                
                sl_r = 0.0
                is_partialed = False
                trade_closed = False
                r_result = 0.0
                
                # Simple Trade Loop
                for j in range(i+1, len(test_df)):
                    m_row = test_df.iloc[j]
                    close = m_row['close']
                    curr_pips = (close - entry_price) / pip_val if sig == 1 else (entry_price - close) / pip_val
                    curr_r = curr_pips / (risk_pips + 1e-9)
                    
                    if not is_partialed and curr_r >= 1.3:
                        is_partialed = True
                        r_result += 0.5 * 1.3
                        sl_r = 0.2
                    
                    if is_partialed:
                        # Max R tracking
                        max_pips = (test_df.iloc[i:j+1]['high'].max() - entry_price) / pip_val if sig == 1 else (entry_price - test_df.iloc[i:j+1]['low'].min()) / pip_val
                        max_r = max_pips / risk_pips
                        
                        # RL State Slopes
                        ema_9_hist = test_df.iloc[max(0, j-10):j+1]['ema_9']
                        slope = (ema_9_hist.iloc[-1] - ema_9_hist.iloc[-4]) / atr_val if len(ema_9_hist) >= 4 else 0
                        
                        action = rl_manager.get_action(curr_r, max_r, slope, m_row['vol'], atr_val / close, sl_r)
                        
                        if action == 1: sl_r += 0.5
                        elif action == 2:
                            r_result += 0.5 * curr_r
                            trade_closed = True; break
                            
                    # Exit Check
                    if is_partialed:
                        if curr_r <= sl_r:
                            r_result += 0.5 * sl_r
                            trade_closed = True; break
                    else:
                        if curr_r <= -1.0:
                            r_result = -1.0
                            trade_closed = True; break
                
                if trade_closed:
                    all_trades.append({"symbol": symbol, "entry_time": entry_time, "r_result": r_result, "risk_pips": risk_pips})
                    last_trade_date = current_date
                    
    if not all_trades:
        print("❌ No trades found in backtest.")
        return
        
    df_results = pd.DataFrame(all_trades).sort_values("entry_time")
    current_bal = STARTING_CAPITAL
    equity_curve = [STARTING_CAPITAL]
    
    for _, trade in df_results.iterrows():
        # Lot floor logic: 0.01 lot = $0.10 per pip
        risk_usd_001 = trade['risk_pips'] * 0.10
        pl_usd = trade['r_result'] * risk_usd_001
        current_bal += pl_usd
        equity_curve.append(current_bal)
    
    total_trades = len(df_results)
    total_return_pct = ((current_bal - STARTING_CAPITAL) / STARTING_CAPITAL) * 100
    win_rate = (df_results['r_result'] > 0).mean() * 100
    equity_series = pd.Series(equity_curve)
    drawdown = (equity_series - equity_series.cummax()) / equity_series.cummax() * 100
    max_dd = drawdown.min()
    
    print("\n" + "="*60)
    print(f"💰 BACKTEST REPORT: $100 MICRO ACCOUNT (1 YEAR)")
    print("="*60)
    print(f"Capital Inicial:    ${STARTING_CAPITAL:.2f}")
    print(f"Capital Final:      ${current_bal:.2f} ({total_return_pct:+.1f}%)")
    print(f"Win Rate:           {win_rate:.1f}%")
    print(f"Max Drawdown:       {max_dd:.1f}%")
    print(f"Total Trades:       {total_trades}")
    print(f"Promedio Riesgo $:  ~${df_results['risk_pips'].mean()*0.10:.2f} ({ (df_results['risk_pips'].mean()*0.10/STARTING_CAPITAL)*100:.1f}%)")
    print("-" * 60)
    if current_bal > STARTING_CAPITAL: print(f"✅ ESTRATEGIA RENTABLE")
    else: print(f"❌ CUENTA EN PÉRDIDA")
    print("="*60 + "\n")

if __name__ == "__main__":
    run_backtest()
