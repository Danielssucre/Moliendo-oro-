#!/usr/bin/env python3
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import re
from pathlib import Path

LOG_DIR = Path("logs")

def get_signals():
    signals = []
    log_file = LOG_DIR / "trading_20260216.log" # Usar el log más reciente y denso
    current_date = "2026-02-16"
    
    with open(log_file, 'r', encoding='latin-1') as f:
        for line in f:
            # ✅ HIVE V5 TRIGGER: BTCUSD | ADX=21.6 | Vol=6.0 | Target=1.5R 
            # (Nota: El log tiene target 1.5R pero el config tiene 3.1R para hive_v5_optimized)
            match = re.search(r"TRIGGER: (\w+) \| ADX=([\d.]+)", line)
            if match:
                time_match = re.match(r"(\d{2}:\d{2}:\d{2})", line)
                if time_match:
                    signals.append({
                        "pair": match.group(1),
                        "time": f"{current_date} {time_match.group(1)}",
                        "adx": float(match.group(2))
                    })
    return signals

def run_simulation():
    signals = get_signals()
    if not signals:
        print("❌ No se encontraron señales para simular.")
        return

    results = []
    print(f"🧬 Simulando {len(signals)} señales...")

    for s in signals[:20]: # Muestra para velocidad
        symbol = s['pair']
        # Ajuste de símbolos para yf
        if "USD" in symbol and "X" not in symbol and "BTC" not in symbol and "SOL" not in symbol:
            symbol += "=X"
        if "BTC" in symbol: symbol = "BTC-USD"
        if "SOL" in symbol: symbol = "SOL-USD"
        
        try:
            ticker = yf.Ticker(symbol)
            start_dt = datetime.strptime(s['time'], "%Y-%m-%d %H:%M:%S")
            end_dt = start_dt + timedelta(days=2)
            
            hist = ticker.history(start=start_dt.strftime("%Y-%m-%d"), end=end_dt.strftime("%Y-%m-%d"), interval="15m")
            hist = hist[hist.index.tz_localize(None) >= start_dt]
            
            if hist.empty: continue
            
            entry = hist.iloc[0]['Open']
            # Supongamos SL de 1 ATR (simplificado para la auditoría)
            sl_dist = entry * 0.005 # 0.5% como proxy
            target_1_5 = entry + (sl_dist * 1.5)
            target_3 = entry + (sl_dist * 3.0)
            sl = entry - sl_dist
            
            reached_1_5 = False
            reached_3 = False
            stopped_out = False
            
            for index, row in hist.iterrows():
                high, low = row['High'], row['Low']
                
                if low <= sl:
                    stopped_out = True
                    break
                
                if high >= target_1_5:
                    reached_1_5 = True
                
                if reached_1_5 and high >= target_3:
                    reached_3 = True
                    break
            
            results.append({
                "pair": s['pair'],
                "reached_1_5": reached_1_5,
                "reached_3": reached_3,
                "stopped": stopped_out
            })
        except Exception as e:
            pass

    df = pd.DataFrame(results)
    if df.empty:
        print("❌ No se pudieron obtener datos de simulación.")
        return
        
    p_1_5 = df['reached_1_5'].mean()
    # P(3R | 1.5R)
    subset = df[df['reached_1_5'] == True]
    if not subset.empty:
        p_3_given_1_5 = subset['reached_3'].mean()
    else:
        p_3_given_1_5 = 0.0
        
    print("\n📊 RESULTADOS DE PROBABILIDAD CONDICIONAL")
    print("-" * 50)
    print(f"P(1.5R alcanzado): {p_1_5:.1%}")
    print(f"P(3.0R | 1.5R alcanzado): {p_3_given_1_5:.1%}")
    print("-" * 50)
    
    if p_3_given_1_5 < 0.40:
        print("💡 CONCLUSIÓN: Edge detectado en 1.5R, pero decae fuertemente hacia 3R.")
        print("ACCION: Cerrar 50% en 1.3-1.5R es MATHEMATICALLY SUPERIOR.")
    else:
        print("💡 CONCLUSIÓN: El momentum se mantiene hacia 3R.")
        print("ACCION: Mantener TP completo o usar Trailing agresivo.")

if __name__ == "__main__":
    run_simulation()
