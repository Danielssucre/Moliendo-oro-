import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

def analyze_recent_performance():
    if not mt5.initialize():
        print("❌ MT5 Init failed")
        return

    # Mirar las últimas 72 horas para tener contexto
    from_date = datetime.now() - timedelta(days=3)
    deals = mt5.history_deals_get(from_date, datetime.now())
    
    if not deals:
        print("📊 No hay deals recientes en el historial.")
        mt5.shutdown()
        return

    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    # Filtrar solo trades cerrados (entry=1 es out, entry=0 es in)
    # En MT5, entry=1 es deal_entry_out
    df = df[df['entry'] == 1] 
    
    if df.empty:
        print("📊 No hay trades cerrados recientes.")
        mt5.shutdown()
        return

    # Clasificar por símbolo y dirección (esto es un proxy, ya que no tenemos los comments viejos con NEM)
    # Pero podemos ver qué activos están rindiendo
    summary = df.groupby('symbol').agg({
        'profit': 'sum',
        'ticket': 'count'
    }).rename(columns={'ticket': 'trades'}).sort_values('profit', ascending=False)
    
    print("\n--- ANALISIS DE RENDIMIENTO RECIENTE (Últimas 72h) ---")
    print(summary)
    
    # Intentar identificar si ganan más en BUY o SELL por símbolo
    direction_summary = df.groupby(['symbol', 'type']).agg({'profit': 'sum'}).unstack()
    print("\n--- RENDIMIENTO POR DIRECCIÓN (0=Buy, 1=Sell) ---")
    print(direction_summary)

    mt5.shutdown()

if __name__ == "__main__":
    analyze_recent_performance()
