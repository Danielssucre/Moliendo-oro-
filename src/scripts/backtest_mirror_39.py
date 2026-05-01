import sys
import os
import pandas as pd
import numpy as np
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.nanobot.ml.polimata_v6 import PolimataGeneral, PolimataDecision

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("REPORT_GEN")

# --- FINAL SNIPER 70/30 SPECS ---
DATA_DIR = "data/historical"
SESSION_START = 6
SESSION_END = 18
RISK_PER_TRADE = 0.005 # 0.5%
INITIAL_BALANCE = 10000.0
SPREAD_PIPS = 1.5 # Average fixed spread penalty



def calculate_indicators(df):
    """Calculates EMA 3/9 and required features for Polimata."""
    df = df.copy()
    df['ema_3'] = df['close'].ewm(span=3, adjust=False).mean()
    df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['ema_800'] = df['close'].ewm(span=800, adjust=False).mean()
    
    # ATR calculation
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    # ADX and RSI required by Polimata's heuristic fallback
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
    
    # RSI calculation
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))

    df['adx'] = dx.ewm(alpha=1/period, adjust=False).mean()
    
    # Slope of EMA 9
    df['ema9_slope'] = df['ema_9'].diff()
    
    return df

def run_backtest():
    polimata = PolimataGeneral(model_path="models/polimata_hmm_v1.pkl")
    
    csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith("_Training_Dataset.csv")]
    if not csv_files:
        logger.error("❌ No historical data found in data/historical")
        return
        
    all_trades = []
    
    for filename in csv_files:
        symbol = filename.split("_")[2]
        path = os.path.join(DATA_DIR, filename)
        logger.info(f"🎯 Sniper Simulation on {symbol}...")
        
        df = pd.read_csv(path)
        df['time'] = pd.to_datetime(df['time'])
        df = df.sort_values("time").reset_index(drop=True)
        df = calculate_indicators(df)
        df = df.dropna().reset_index(drop=True)
        
        if len(df) < 800: continue # Need enough for EMA 800
        
        pip_size = 0.01 if "JPY" in symbol else 0.0001
        spread_cost = SPREAD_PIPS * pip_size
        
        # Precompute signal array
        df['prev_ema3'] = df['ema_3'].shift(1)
        df['prev_ema9'] = df['ema_9'].shift(1)
        
        cross_up = (df['prev_ema3'] <= df['prev_ema9']) & (df['ema_3'] > df['ema_9'])
        cross_down = (df['prev_ema3'] >= df['prev_ema9']) & (df['ema_3'] < df['ema_9'])
        signal_indices = df[cross_up | cross_down].index
        
        # SNIPER: Cooldown tracking
        last_trade_day = None
        
        for idx in signal_indices:
            if idx < 800 or idx >= len(df) - 1: continue
            
            current_day = df['time'].iloc[idx].date()
            if last_trade_day == current_day: continue # 1 Trade/Day Limit
            
            sig = 1 if cross_up.loc[idx] else -1
            row = df.iloc[idx]
            
            # --- SNIPER FILTER: TREND ANCHOR ---
            # Thesis only aligned with EMA 200 and EMA 800
            is_uptrend = row['close'] > row['ema_200'] and row['ema_200'] > row['ema_800']
            is_downtrend = row['close'] < row['ema_200'] and row['ema_200'] < row['ema_800']
            
            # --- SNIPER FILTER: MOMENTUM (SLOPE) ---
            slope_ok = (sig == 1 and row['ema9_slope'] > 0) or (sig == -1 and row['ema9_slope'] < 0)
            if not slope_ok: continue
            
            # --- SNIPER FILTER: GAP/CLEARANCE ---
            prev_rows = df.iloc[idx-5:idx]
            max_gap = abs(prev_rows['ema_3'] - prev_rows['ema_9']).max()
            if max_gap < (row['atr'] * 0.2): continue # Ignore noisy/tight crosses
            
            entry_price = df['open'].iloc[idx+1]
            context_df = df.iloc[idx-100:idx+1].copy()
            
            # Evaluate with Polimata
            decision_tesis = polimata.evaluate_signal(symbol, sig, "TESIS", context_df)
            decision_antitesis = polimata.evaluate_signal(symbol, -sig, "ANTITESIS", context_df)
            
            # SNIPER DECISION:
            # 1. TESIS ONLY in Trend
            # 2. ANTITESIS ONLY in ranging or if far from EMA 200
            approved_decision = None
            active_sig = 0
            tag = ""
            
            if sig == 1 and is_uptrend and decision_tesis.approved:
                approved_decision = decision_tesis; active_sig = sig; tag = "TESIS_UP"
            elif sig == -1 and is_downtrend and decision_tesis.approved:
                approved_decision = decision_tesis; active_sig = sig; tag = "TESIS_DOWN"
            elif decision_antitesis.approved:
                # Anti-Trend Reversion
                approved_decision = decision_antitesis; active_sig = -sig; tag = "ANTITESIS"
                
            if approved_decision is None: continue
                
            last_trade_day = current_day # Confirm sniper lock
            
            actual_entry = entry_price + (spread_cost if active_sig == 1 else -spread_cost)
            sl_dist = row['atr'] * 1.5
            sl = actual_entry - sl_dist if active_sig == 1 else actual_entry + sl_dist
            
            tp1_dist = sl_dist * approved_decision.adjusted_rr
            tp1 = actual_entry + (tp1_dist if active_sig == 1 else -tp1_dist)
            
            has_runner = approved_decision.extended_rr > 0
            tp2_dist = sl_dist * (approved_decision.extended_rr if has_runner else approved_decision.adjusted_rr)
            tp2 = actual_entry + (tp2_dist if active_sig == 1 else -tp2_dist)
            
            # Forward simulation
            pnl_r_total = 0
            t70_closed = False
            t30_closed = False
            
            for f_idx in range(idx+1, len(df)):
                fr = df.iloc[f_idx]
                h, l = fr['high'], fr['low']
                
                # Ticket 70% (Base)
                if not t70_closed:
                    hit_sl = (l <= sl) if active_sig == 1 else (h >= sl)
                    hit_tp = (h >= tp1) if active_sig == 1 else (l <= tp1)
                    if hit_tp:
                        pnl_r_total += approved_decision.adjusted_rr * 0.7
                        t70_closed = True
                        sl = actual_entry # Move Runner to BE
                    elif hit_sl:
                        pnl_r_total -= 0.7
                        t70_closed = True
                        t30_closed = True # Stop out full pos
                        
                # Ticket 30% (Runner)
                if has_runner and not t30_closed:
                    hit_tp2 = (h >= tp2) if active_sig == 1 else (l <= tp2)
                    hit_sl2 = (l <= sl) if active_sig == 1 else (h >= sl)
                    if hit_tp2:
                        pnl_r_total += approved_decision.extended_rr * 0.3
                        t30_closed = True
                    elif hit_sl2:
                        # If sl is actual_entry, it's 0 loss, otherwise -0.3
                        pnl_r_total += (0.0 if sl == actual_entry else -0.3)
                        t30_closed = True
                elif not has_runner:
                    t30_closed = True # No runner logic
                        
                if t70_closed and t30_closed: break

            all_trades.append({
                'symbol': symbol, 'time': df['time'].iloc[idx+1], 'type': tag,
                'pnl_r': pnl_r_total, 'regime': approved_decision.regime
            })

    if not all_trades:
        print("❌ Sniper is too strict! No trades found.")
        return
        
    res_df = pd.DataFrame(all_trades)
    dollar_risk = INITIAL_BALANCE * RISK_PER_TRADE
    res_df['dollar_pnl'] = res_df['pnl_r'] * dollar_risk
    res_df['balance'] = INITIAL_BALANCE + res_df['dollar_pnl'].cumsum()

    
    print("\n" + "="*80)
    print("🎯 SNIPER BACKTEST V2: INSTITUTIONAL MIRROR 3-9")
    print("="*80)
    print(f"Total Trades: {len(res_df)} (Reducción dramática del ruido!)")
    print(f"Win Rate: {(res_df['pnl_r'] > 0).mean()*100:.2f}%")
    print(f"Expected Profit: {res_df['pnl_r'].sum():.2f} R")
    print(f"Final Balance: ${res_df['balance'].iloc[-1]:,.2f}")
    
    print("\n📊 RESULTADOS POR CATEGORÍA")
    print(res_df.groupby('type')['pnl_r'].agg(['count', 'sum', 'mean']))
    
    res_df.to_csv("data/research/backtest_sniper_v2_results.csv", index=False)
    print(f"\n✅ Reporte Sniper guardado: data/research/backtest_sniper_v2_results.csv")

if __name__ == "__main__":
    run_backtest()
