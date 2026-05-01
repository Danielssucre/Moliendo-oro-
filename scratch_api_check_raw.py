import requests
import time

print("Polling API Backend...")
for _ in range(15):
    try:
        res = requests.get('http://localhost:8000/stats')
        data = res.json()
        orders = data.get('active_positions', [])
        
        buys = 0
        sells = 0
        for o in orders:
            if 'buy' in str(o.get('type', '')).lower(): buys += 1
            elif 'sell' in str(o.get('type', '')).lower(): sells += 1
            
        print(f"BUYS: {buys} | SELLS: {sells} | PENDIENTES: {len(orders)}")
        if buys > 0:
            print("🚀 ¡ÓRDENES DE COMPRA DETECTADAS CON ÉXITO!")
            break
            
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(2)
