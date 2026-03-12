
import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_duelo_live():
    from siliconmetatrader5 import MetaTrader5
    import json
    
    port = 8001
    mt5 = MetaTrader5(port=port)
    
    # Credentials
    try:
        with open('config/credentials.json') as f:
            creds = json.load(f)['mt5']
            c_login = creds['account']
            c_pass = creds['password']
            c_server = creds['server']
    except:
        c_login = 1512629315
        c_pass = "@zn49Hw4W2*"
        c_server = "FTMO-Demo"

    print("🔗 Conectando a MetaTrader 5 (Nativo)...")
    if not mt5.initialize(path='C:\\Program Files\\MetaTrader 5\\terminal64.exe', portable=True, login=c_login, password=c_pass, server=c_server):
        print(f"❌ Error al inicializar MT5: {mt5.last_error()}")
        return

    symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY"]
    timeframes = [mt5.TIMEFRAME_M15]
    days_back = 30
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    results = {
        "1.50": {"trades": [], "wins": 0, "total_r": 0},
        "1.35": {"trades": [], "wins": 0, "total_r": 0}
    }

    print(f"📊 Extrayendo historial (M15) de {len(symbols)} pares para los últimos {days_back} días...")
    
    for symbol in symbols:
        print(f"  - Procesando {symbol}...", end="\r")
        mt5.symbol_select(symbol, True)
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, start_date, end_date)
        
        if rates is None or len(rates) < 100:
            continue
            
        df = pd.DataFrame(rates)
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_15'] = df['close'].ewm(span=15, adjust=False).mean()
        
        # ATR calculation
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()
        df = df.dropna().reset_index(drop=True)

        for rr_label in ["1.50", "1.35"]:
            rr_val = float(rr_label)
            
            for i in range(50, len(df) - 50):
                row = df.iloc[i]
                sig = 0
                if row['ema_9'] > row['ema_15'] and row['close'] > row['ema_200']: sig = 1
                elif row['ema_9'] < row['ema_15'] and row['close'] < row['ema_200']: sig = -1
                
                if sig == 0: continue
                
                entry_price = df.iloc[i+1]['open']
                sl_dist = row['atr'] * 1.5 # Using your bot's multiplier 1.5
                tp_dist = sl_dist * rr_val
                
                sl = entry_price - sl_dist if sig == 1 else entry_price + sl_dist
                tp = entry_price + tp_dist if sig == 1 else entry_price - tp_dist
                
                outcome = 0
                for j in range(i+1, min(i+100, len(df))):
                    f_row = df.iloc[j]
                    if sig == 1:
                        if f_row['low'] <= sl: outcome = -1; break
                        if f_row['high'] >= tp: outcome = rr_val; break
                    else:
                        if f_row['high'] >= sl: outcome = -1; break
                        if f_row['low'] <= tp: outcome = rr_val; break
                
                if outcome != 0:
                    results[rr_label]["trades"].append(outcome)
                    i += 8 # Avoid excessive overlap

    mt5.shutdown()
    
    print("\n" + "="*70)
    print(f"🏆 VERDICTO FINAL: DATA EN VIVO DE MT5 ({days_back} DÍAS)")
    print("="*70)
    print(f"{'Métrica':<25} | {'Actual (1:1.50)':<20} | {'LYRA (1:1.35)':<20}")
    print("-" * 70)
    
    for label in ["1.50", "1.35"]:
        data = results[label]
        trades = np.array(data["trades"])
        n = len(trades)
        if n > 0:
            wr = len(trades[trades > 0]) / n
            r_total = np.sum(trades)
            pf = np.sum(trades[trades > 0]) / abs(np.sum(trades[trades < 0])) if any(trades < 0) else 0
            results[label].update({"n": n, "wr": wr, "r": r_total, "pf": pf})
        else:
            results[label].update({"n": 0, "wr": 0, "r": 0, "pf": 0})

    r1 = results["1.50"]
    r2 = results["1.35"]
    
    print(f"{'Total Trades':<25} | {r1['n']:<20} | {r2['n']:<20}")
    print(f"{'Win Rate (%)':<25} | {r1['wr']:<20.1%} | {r2['wr']:<20.1%}")
    print(f"{'Rentabilidad Total (R)':<25} | {r1['r']:<20.2f} | {r2['r']:<20.2f}")
    print(f"{'Profit Factor':<25} | {r1['pf']:<20.2f} | {r2['pf']:<20.2f}")
    print("="*70)
    
    if r2['r'] > r1['r']:
        print(f"\n✅ RECOMENDACIÓN: Los datos REALES de tu MT5 confirman que LYRA-135")
        print(f"   es un {((r2['r']-r1['r'])/abs(r1['r']+1e-9))*100:.1f}% mejor en este mercado.")
    else:
        print("\n⚠️ RESULTADO: Tu configuración actual (1.50) sigue siendo superior")
        print("   con los datos directos de tu terminal MT5.")
    print("="*70 + "\n")

if __name__ == "__main__":
    run_duelo_live()
