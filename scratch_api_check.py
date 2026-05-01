import requests
import json

try:
    res = requests.get('http://localhost:8000/stats')
    data = res.json()
    orders = data.get('active_positions', [])
    history = data.get('trade_history', [])
    
    buys = sum(1 for o in orders if o.get('type') == 'buy')
    sells = sum(1 for o in orders if o.get('type') == 'sell')
    buy_limits = sum(1 for o in orders if o.get('type') == 'buy limit')
    sell_limits = sum(1 for o in orders if o.get('type') == 'sell limit')
    buy_stops = sum(1 for o in orders if o.get('type') == 'buy stop')
    sell_stops = sum(1 for o in orders if o.get('type') == 'sell stop')
    
    total_buys = buys + buy_limits + buy_stops
    total_sells = sells + sell_limits + sell_stops
    
    print(f"--- REPORTE OFICIAL DEL BACKEND (PUERTO 8000) ---")
    print(f"Total Órdenes/Posiciones Activas : {len(orders)}")
    print(f"📥 Dirección de COMPRA (BUY)     : {total_buys}")
    print(f"   - Buy Market : {buys}")
    print(f"   - Buy Limit  : {buy_limits}")
    print(f"   - Buy Stop   : {buy_stops}")
    print(f"")
    print(f"📤 Dirección de VENTA (SELL)     : {total_sells}")
    print(f"   - Sell Market: {sells}")
    print(f"   - Sell Limit : {sell_limits}")
    print(f"   - Sell Stop  : {sell_stops}")
    
    print("\nÚLTIMAS LÍNEAS DEL MOTOR:")
    for line in data.get('last_log_lines', [])[-5:]:
        print(line.strip())
        
except Exception as e:
    print(f"Error fetching API: {e}")
