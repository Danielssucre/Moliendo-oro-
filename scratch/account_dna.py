import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, time

def get_symbol_affinity_data():
    if not mt5.initialize():
        return "MT5 Error"

    # 1. Analizar Historia de HOY (Cerrados)
    today_start = datetime.combine(datetime.now().date(), time(0, 0))
    history_deals = mt5.history_deals_get(today_start, datetime.now())
    
    # 2. Analizar Posiciones ABIERTAS (Flotante)
    positions = mt5.positions_get()
    
    print("\n--- [RELOJ BIOLÓGICO DE LA CUENTA] ---")
    
    # Procesar Historia
    if history_deals:
        df_hist = pd.DataFrame(list(history_deals), columns=history_deals[0]._asdict().keys())
        df_hist = df_hist[df_hist['entry'] == 1] # Solo salidas
        if not df_hist.empty:
            hist_perf = df_hist.groupby('symbol')['profit'].sum().sort_values()
            print("\nRESULTADOS CERRADOS HOY:")
            print(hist_perf)
    
    # Procesar Posiciones
    if positions:
        df_pos = pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())
        pos_perf = df_pos.groupby('symbol')['profit'].sum().sort_values()
        print("\nFLOTANTE ACTUAL (Riesgo en vivo):")
        print(pos_perf)
        
    mt5.shutdown()

if __name__ == "__main__":
    get_symbol_affinity_data()
