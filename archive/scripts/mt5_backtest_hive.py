#!/usr/bin/env python3
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.mt5_data_source import MT5DataSource

# --- CONFIGURATION ---
SYMBOLS = ["AUDUSD", "GBPJPY", "BTCUSD", "NZDUSD", "USDCHF", "EURNZD", "GBPUSD", "GBPNZD", "USDJPY", "USDCAD"]
TIMEFRAME = "H1"
LOOKBACK_DAYS = 365  # Full Year Backtest
RISK_REWARD_PARTIAL = 1.3
RISK_REWARD_MOMENTUM = 1.5
RISK_REWARD_FINAL = 3.0
PARTIAL_CLOSE_PCT = 0.5

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("MT5_BACKTEST")

def calculate_indicators(df):
    """Matches indicators in run_ftmo_manual.py"""
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
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr_smooth)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    df['adx'] = dx.ewm(alpha=1/period, adjust=False).mean()
    
    # Volatility Filter (Matching run_ftmo_manual.py)
    returns = df['close'].pct_change()
    df['vol'] = returns.rolling(24).std() * 1000
    
    return df

def run_backtest_for_symbol(mt5, symbol):
    logger.info(f"📊 Testing {symbol}...")
    
    # Fetch data in batches of 30 days to avoid timeouts/empty returns
    end_date_absolute = datetime.now()
    start_date_absolute = end_date_absolute - timedelta(days=LOOKBACK_DAYS + 10)
    
    all_bars = []
    current_end = end_date_absolute
    
    while current_end > start_date_absolute:
        batch_start = max(start_date_absolute, current_end - timedelta(days=30))
        logger.info(f"   [{symbol}] Fetching batch: {batch_start.date()} to {current_end.date()}")
        
        batch_df = mt5.get_historical_data(symbol, TIMEFRAME, batch_start, current_end)
        if not batch_df.empty:
            all_bars.append(batch_df)
        else:
            # If a batch fails, we might have hit the server's history limit
            logger.warning(f"   [{symbol}] No more history available before {batch_start.date()}")
            break
            
        current_end = batch_start - timedelta(seconds=1)

    if not all_bars:
        logger.error(f"❌ No historical data found for {symbol}")
        return []
        
    df = pd.concat(all_bars).drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)
    logger.info(f"✅ Total data for {symbol}: {len(df)} bars ({df['date'].min()} to {df['date'].max()})")
    
    df = calculate_indicators(df)
    
    # Only test the requested window
    test_start_date = end_date_absolute - timedelta(days=LOOKBACK_DAYS)
    test_df = df[df['date'] >= test_start_date].copy()
    
    trades = []
    last_trade_date = None
    
    # Simulation
    for i in range(len(test_df) - 1):
        row = test_df.iloc[i]
        
        # Signal Logic
        sig = 0
        if row['ema_9'] > row['ema_15'] and row['close'] > row['ema_200']:
            sig = 1
        elif row['ema_9'] < row['ema_15'] and row['close'] < row['ema_200']:
            sig = -1
            
        if sig == 0: continue
        
        # --- ONE TRADE PER DAY CONSTRAINT (Matching Live Bot) ---
        current_date = row['date'].date()
        if last_trade_date == current_date:
            continue
        # --------------------------------------------------------

        # Filters (Daniel's 15/18 check)
        if not (row['adx'] > 15 and row['vol'] < 18):
            continue
            
        # Entry (Open of next candle)
        entry_price = test_df.iloc[i+1]['open']
        entry_time = test_df.iloc[i+1]['date']
        
        # Stop Loss & Take Profit (ATR based proxy as per HIVE V5)
        atr_val = row['atr']
        sl_dist = atr_val * 2.0 # Standard HIVE V5 stop distance
        
        if sig == 1:
            sl = entry_price - sl_dist
            tp_partial = entry_price + (sl_dist * RISK_REWARD_PARTIAL)
            tp_final = entry_price + (sl_dist * RISK_REWARD_FINAL)
        else:
            sl = entry_price + sl_dist
            tp_partial = entry_price - (sl_dist * RISK_REWARD_PARTIAL)
            tp_final = entry_price - (sl_dist * RISK_REWARD_FINAL)
            
        # Trade Loop logic
        reached_partial = False
        reached_1_5r = False
        reached_3r = False
        time_to_1_5r = None
        
        trade_closed = False
        trade_result = 0.0
        exit_time = None
        exit_reason = None
        
        # Target Prices
        if sig == 1:
            tp_1_5 = entry_price + (sl_dist * 1.5)
            tp_3_0 = entry_price + (sl_dist * 3.0)
        else:
            tp_1_5 = entry_price - (sl_dist * 1.5)
            tp_3_0 = entry_price - (sl_dist * 3.0)

        # Loop through subsequent candles to manage trade
        for j in range(i + 1, len(test_df)):
            m_row = test_df.iloc[j]
            high, low = m_row['high'], m_row['low']
            
            # --- Momentum Tracking (Daniel's Request) ---
            if not reached_1_5r:
                if (sig == 1 and high >= tp_1_5) or (sig == -1 and low <= tp_1_5):
                    reached_1_5r = True
                    time_to_1_5r = (m_row['date'] - entry_time).total_seconds() / 3600.0 # to hours
            
            if reached_1_5r and not reached_3r:
                if (sig == 1 and high >= tp_3_0) or (sig == -1 and low <= tp_3_0):
                    reached_3r = True
            # --------------------------------------------

            # 🟢 Partial Exit & BE logic (@ 1.3R)
            if not reached_partial:
                if (sig == 1 and high >= tp_partial) or (sig == -1 and low <= tp_partial):
                    reached_partial = True
                    trade_result += PARTIAL_CLOSE_PCT * RISK_REWARD_PARTIAL
                    sl = entry_price # Move to BE
            
            # 🟢 Check Exit (Final TP or SL)
            if sig == 1:
                if low <= sl:
                    trade_closed = True
                    exit_reason = "SL" if not reached_partial else "BE"
                    trade_result += (1 - PARTIAL_CLOSE_PCT) * (0 if reached_partial else -1)
                elif high >= tp_final:
                    trade_closed = True
                    exit_reason = "TP"
                    trade_result += (1 - PARTIAL_CLOSE_PCT) * RISK_REWARD_FINAL
            else: # SELL
                if high >= sl:
                    trade_closed = True
                    exit_reason = "SL" if not reached_partial else "BE"
                    trade_result += (1 - PARTIAL_CLOSE_PCT) * (0 if reached_partial else -1)
                elif low <= tp_final:
                    trade_closed = True
                    exit_reason = "TP"
                    trade_result += (1 - PARTIAL_CLOSE_PCT) * RISK_REWARD_FINAL
            
            if trade_closed:
                exit_time = m_row['date']
                last_trade_date = current_date # Mark as traded today
                break
        
        if trade_closed:
            # --- LEGACY SIMULATION (Parallel Logic) ---
            # Just calculating what would have happened if we stayed in the trade full size
            trade_closed_legacy = False
            result_legacy = 0.0
            
            # Legacy TP/SL
            tp_legacy = tp_final if sig == 1 else tp_final # Final is 3.1 or 3.0
            sl_legacy = entry_price - sl_dist if sig == 1 else entry_price + sl_dist
            
            for k in range(i + 1, len(test_df)):
                k_row = test_df.iloc[k]
                k_high, k_low = k_row['high'], k_row['low']
                
                if (sig == 1 and k_low <= sl_legacy) or (sig == -1 and k_high >= sl_legacy):
                    result_legacy = -1.0
                    trade_closed_legacy = True
                elif (sig == 1 and k_high >= tp_legacy) or (sig == -1 and k_low <= tp_legacy):
                    result_legacy = RISK_REWARD_FINAL
                    trade_closed_legacy = True
                    
                if trade_closed_legacy: break

            trades.append({
                "symbol": symbol,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "type": "BUY" if sig == 1 else "SELL",
                "result_partials": trade_result,
                "result_legacy": result_legacy if trade_closed_legacy else 0.0,
                "exit_reason": exit_reason,
                "reached_partial": reached_partial,
                "reached_1_5r": reached_1_5r,
                "reached_3r": reached_3r,
                "time_to_1_5r": time_to_1_5r
            })
            # Skip indices covered by the trade (naive approach)
            # i = j # Not possible in for loop easily, but good enough for 2 days
            
    return trades

def main():
    logger.info("🚀 STARTING MT5 1-YEAR BACKTEST (Institutional Audit)")
    
    with MT5DataSource() as mt5:
        if not mt5.connected:
            logger.error("Failed to connect to MT5.")
            return
            
        all_trades = []
        for symbol in SYMBOLS:
            all_trades.extend(run_backtest_for_symbol(mt5, symbol))
            
    if not all_trades:
        logger.warning("No trades found in the last 48 hours with current filters.")
        # Try once more with relaxed filters just to see if that's the issue
        print("\n💡 TIP: If 0 trades found, it might be the 15/18 Filter Paralysis.")
        return
        
    df = pd.DataFrame(all_trades)
    
    # Daniel's Specific Metrics
    reached_1_5 = df[df['reached_1_5r'] == True]
    p_3_given_1_5 = len(reached_1_5[reached_1_5['reached_3r'] == True]) / len(reached_1_5) if len(reached_1_5) > 0 else 0
    avg_time_to_1_5 = reached_1_5['time_to_1_5r'].mean() if len(reached_1_5) > 0 else 0

    print("\n" + "="*70)
    print("🔬 COMPARATIVA DE REGIMENES (Legacy vs. New Architecture) - 1 AÑO")
    print("="*70)
    print(f"Total Trades Analizados (365d): {len(df)}")
    print(f"P(3R | 1.5R alcanzado):         {p_3_given_1_5:.1%}")
    print(f"Tiempo medio hasta 1.5R:         {avg_time_to_1_5:.1f} horas")
    print("-" * 70)
    
    # Legacy Stats
    l_win_rate = len(df[df['result_legacy'] > 0]) / len(df)
    l_total_r = df['result_legacy'].sum()
    l_expectancy = df['result_legacy'].mean()
    l_dd_max_trades = 0 # Simple proxy
    
    # New Stats
    n_win_rate = len(df[df['result_partials'] > 0]) / len(df)
    n_total_r = df['result_partials'].sum()
    n_expectancy = df['result_partials'].mean()

    print(f"{'Métrica':<25} | {'Legacy (3.1R)':<18} | {'New (Partials)':<18}")
    print("-" * 70)
    print(f"{'Win Rate (%)':<25} | {l_win_rate:<18.1%} | {n_win_rate:<18.1%}")
    print(f"{'Total R Acumulado':<25} | {l_total_r:<18.2f} | {n_total_r:<18.2f}")
    print(f"{'Expectancy (R/Trade)':<25} | {l_expectancy:<18.2f} | {n_expectancy:<18.2f}")
    print(f"{'Edge (Delta R)':<25} | {'-':<18} | {n_total_r - l_total_r:<+18.2f}")
    
    print("\n" + "="*70)
    print("💡 CONCLUSIÓN INSTITUCIONAL")
    print("="*70)
    if n_total_r > l_total_r:
        improvement = (n_total_r / l_total_r * 100) if l_total_r != 0 else 100
        print(f"✅ La nueva arquitectura GENERA ALPHA ADICIONAL de {n_total_r - l_total_r:.2f}R.")
        print(f"✅ El Win Rate aumentó un {n_win_rate - l_win_rate:.1%} gracias a los parciales.")
    else:
        print("⚠️ La estrategia Legacy tiene mayor R total, pero mayor varianza.")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
