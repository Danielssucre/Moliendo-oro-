
import pandas as pd
import numpy as np
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_duelo_lyra():
    csv_path = "/Users/danielsuarezsucre/TRADING/trading_agent/data/historical/BACKTEST_DATA.csv"
    if not os.path.exists(csv_path):
        print(f"❌ Error: No se encontró el archivo en {csv_path}")
        return

    print(f"📖 Cargando dataset profesional: {os.path.basename(csv_path)}...")
    df = pd.read_csv(csv_path)
    df.columns = [c.lower() for c in df.columns]
    
    # Use existing columns from the professional dataset
    # We'll use the provided EMA_20, EMA_50, EMA_200 and ATR/ADX
    if 'ema_20' in df.columns:
        df['ema_9'] = df['ema_20'] # Proxy
    if 'ema_50' in df.columns:
        df['ema_15'] = df['ema_50'] # Proxy

    def simulate_strategy(rr_target):
        trades = []
        # Simulation Loop
        for i in range(50, len(df) - 50):
            row = df.iloc[i]
            # Simple Trend signal based on the dataset metrics
            sig = 0
            if row['close'] > row['ema_200'] and row['ema_20'] > row['ema_50']:
                sig = 1
            elif row['close'] < row['ema_200'] and row['ema_20'] < row['ema_50']:
                sig = -1
            
            if sig == 0: continue
            
            # Entry
            entry_price = df.iloc[i+1]['open']
            sl_dist = row['atr'] if row['atr'] > 0 else 0.0020 # Fallback
            tp_dist = sl_dist * rr_target
            
            sl = entry_price - sl_dist if sig == 1 else entry_price + sl_dist
            tp = entry_price + tp_dist if sig == 1 else entry_price - tp_dist
            
            # Outcome
            result = 0
            for j in range(i+1, min(i+100, len(df))):
                f_row = df.iloc[j]
                if sig == 1:
                    if f_row['low'] <= sl: result = -1; break
                    if f_row['high'] >= tp: result = rr_target; break
                else:
                    if f_row['high'] >= sl: result = -1; break
                    if f_row['low'] <= tp: result = rr_target; break
            
            if result != 0:
                trades.append(result)
                i += 10 # Avoid overlap
        
        if not trades: return 0, 0, 0, 0
        
        trades = np.array(trades)
        win_rate = len(trades[trades > 0]) / len(trades)
        total_r = np.sum(trades)
        profit_factor = np.sum(trades[trades > 0]) / abs(np.sum(trades[trades < 0])) if any(trades < 0) else 0
        
        return len(trades), win_rate, total_r, profit_factor

    print("\n" + "="*60)
    print("⚔️  DUELO DE ESTADÍSTICAS: CONFIGURACIÓN ACTUAL vs LYRA-135")
    print("   Dataset: EURUSD Professional (6.3MB)")
    print("="*60)
    
    # RUN CURRENT (Using 1.5 as base)
    n1, wr1, r1, pf1 = simulate_strategy(1.5)
    
    # RUN LYRA (1.35)
    n2, wr2, r2, pf2 = simulate_strategy(1.35)
    
    # Actualizing with a third test (Targeting 1:2.0 as seen in some profiles)
    n3, wr3, r3, pf3 = simulate_strategy(2.0)
    
    print(f"{'Métrica':<20} | {'Ratio 1:1.50':<18} | {'LYRA (1:1.35)':<18}")
    print("-" * 60)
    print(f"{'Total Trades':<20} | {n1:<18} | {n2:<18}")
    print(f"{'Win Rate (%)':<20} | {wr1:<18.1%} | {wr2:<18.1%}")
    print(f"{'Rentabilidad (R)':<20} | {r1:<18.2f} | {r2:<18.2f}")
    print(f"{'Profit Factor':<20} | {pf1:<18.2f} | {pf2:<18.2f}")
    print("-" * 60)
    print(f"{'Ratio 1:2.00 (Ref)':<20} | {wr3:<18.1%} | {r3:<18.2f}R")
    print("="*60)
    
    if r2 > r1:
        print(f"\n✅ RECOMENDACIÓN: El modelo LYRA-135 es superior en {(r2-r1)/abs(r1)*100:.1f}% de rentabilidad.")
    else:
        print("\n⚠️ RESULTADO: El ratio 1.5 actual genera más beneficio total en esta muestra.")
    print("="*60 + "\n")

if __name__ == "__main__":
    run_duelo_lyra()
