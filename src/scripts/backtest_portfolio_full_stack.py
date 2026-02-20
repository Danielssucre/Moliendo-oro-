
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
from src.nanobot.ml.risk_oracle import AsymmetricRiskOracle

# --- CONFIGURATION ---
SYMBOLS = ["USDCAD", "USDCHF", "AUDUSD", "EURNZD"]
TIMEFRAME = "H1"
LOOKBACK_DAYS = 365

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("PORTFOLIO_BACKTEST")

def calculate_indicators(df):
    df = df.copy()
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    period = 14
    atr_smooth = tr.ewm(alpha=1/period, adjust=False).mean()
    up = df['high'].diff(); down = -df['low'].diff()
    plus_dm = pd.Series(0.0, index=df.index); minus_dm = pd.Series(0.0, index=df.index)
    plus_dm[(up > down) & (up > 0)] = up[(up > down) & (up > 0)]
    minus_dm[(down > up) & (down > 0)] = down[(down > up) & (down > 0)]
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / (atr_smooth + 1e-9))
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / (atr_smooth + 1e-9))
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)
    df['adx'] = dx.ewm(alpha=1/period, adjust=False).mean()
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    returns = df['close'].pct_change()
    df['vol'] = returns.rolling(24).std() * 1000
    
    return df

def run_portfolio_bt():
    stop_hunt_model = StopHuntModel()
    risk_oracle = AsymmetricRiskOracle() # Will use lazy loading for specialists
    
    all_trades = []
    
    print("\n" + "="*90)
    print(f"🛰️  MASTER PORTFOLIO BACKTEST: FULL STACK RL (11 PARES - 1 AÑO)")
    print("="*90)
    print(f"{'Símbolo':<10} | {'Trades':<6} | {'W.R.':<8} | {'RL Expectancy':<15} | {'PnL (R)':<10}")
    print("-" * 90)

    with MT5DataSource() as mt5:
        if not mt5.connected: return

        for symbol in SYMBOLS:
            print(f"🔬 Simulando {symbol}...")
            # Fetch and Prepare Data
            end_date_abs = datetime.now()
            start_date_abs = end_date_abs - timedelta(days=LOOKBACK_DAYS + 10)
            
            all_bars = []
            current_end = end_date_abs
            while current_end > start_date_abs:
                batch_start = max(start_date_abs, current_end - timedelta(days=30))
                batch_df = mt5.get_historical_data(symbol, TIMEFRAME, batch_start, current_end)
                if not batch_df.empty: all_bars.append(batch_df)
                else: break
                current_end = batch_start - timedelta(seconds=1)

            if not all_bars: continue
            df = pd.concat(all_bars).drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)
            df = calculate_indicators(df)
            df = df.dropna().reset_index(drop=True)

            total_signals = 0
            tech_rejected = 0
            ai_rejected = 0
            rl_pruned = 0
            symbol_trades = []
            last_trade_date = None

            for i in range(50, len(df) - 48):
                row = df.iloc[i]
                
                # Signal logic
                sig = 0
                if row['ema_9'] > row['ema_15'] and row['close'] > row['ema_200']: sig = 1
                elif row['ema_9'] < row['ema_15'] and row['close'] < row['ema_200']: sig = -1
                if sig == 0: continue
                
                total_signals += 1
                current_date = row['date'].date()
                if last_trade_date == current_date: continue

                # Filters
                thresholds = {"EURUSD": 0.45, "GBPUSD": 0.65}
                pair_threshold = thresholds.get(symbol, 0.85)
                
                tech_pass = (row['adx'] > 15 and row['vol'] < 18)
                if not tech_pass:
                    tech_rejected += 1
                    continue

                inds = {'rsi': row['rsi'], 'adx': row['adx'], 'atr': row['atr'], 'vwap': row['close']}
                features = stop_hunt_model.extract_features(df.iloc[:i+1], row['close'], inds)
                ml_risk = stop_hunt_model.predict_risk(features)
                prob_success = 1.0 - ml_risk
                ml_pass = (ml_risk < pair_threshold)

                if not ml_pass:
                    ai_rejected += 1
                    continue

                # RL Specialist Multiplier
                rl_mult = risk_oracle.calculate_sizing_multiplier(
                    probability=prob_success, adx=row['adx'], rsi=row['rsi'], 
                    vol=row['vol'], current_dd=0.0, symbol=symbol
                )
                
                if rl_mult <= 0.0:
                    rl_pruned += 1
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
                        if f_row['high'] >= tp: outcome_r = 1.5; found = True; break
                    else:
                        if f_row['high'] >= sl: break
                        if f_row['low'] <= tp: outcome_r = 1.5; found = True; break
                
                if not found:
                    final_price = df.iloc[i+47]['close']
                    outcome_r = ((final_price - entry_price) / sl_dist) if sig == 1 else ((entry_price - final_price) / sl_dist)

                final_r = outcome_r * rl_mult
                symbol_trades.append({"symbol": symbol, "date": row['date'], "raw_r": outcome_r, "rl_mult": rl_mult, "final_r": final_r})
                last_trade_date = current_date

            if symbol_trades:
                stdf = pd.DataFrame(symbol_trades)
                wr = len(stdf[stdf['raw_r'] > 0]) / len(stdf)
                total_pnl = stdf['final_r'].sum()
                avg_r = stdf['final_r'].mean()
                print(f"{symbol:<10} | {len(stdf):<6} | {wr:<8.1%} | {avg_r:<15.2f}R | {total_pnl:>10.2f}R | (Pruned: {rl_pruned})")
                all_trades.extend(symbol_trades)
            else:
                print(f"{symbol:<10} | 0      | 0%       | 0.00            | 0.00R       | (Pruned: {rl_pruned})")

    if not all_trades:
        print("\n❌ No trades found after all filters.")
        return

    tdf = pd.DataFrame(all_trades)
    print("\n" + "="*90)
    print("📊 RESULTADOS CONSOLIDADOS DEL PORTAFOLIO")
    print("-" * 90)
    print(f"Total Trades:       {len(tdf)}")
    print(f"Win Rate Promedio:   {len(tdf[tdf['raw_r'] > 0]) / len(tdf):.1%}")
    print(f"Rentabilidad Total:  {tdf['final_r'].sum():.2f}R")
    print(f"Expectativa Promedio:{tdf['final_r'].mean():.2f}R por señal")
    print(f"Max Portfolio DD (R):{ (tdf.sort_values('date')['final_r'].cumsum().cummax() - tdf.sort_values('date')['final_r'].cumsum()).max():.2f}R")
    print("="*90 + "\n")

if __name__ == "__main__":
    run_portfolio_bt()
