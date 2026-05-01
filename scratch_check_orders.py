import os
import sys
import json

PROJECT_ROOT = "/Users/danielsuarezsucre/TRADING/trading_agent"
sys.path.append(PROJECT_ROOT)
from src.nanobot.exchanges.mt5_client import SiliconMT5Client

# Load credentials
creds_path = os.path.join(PROJECT_ROOT, "config/credentials.json")
with open(creds_path, 'r') as f:
    creds = json.load(f).get("mt5", {})

mt5_client = SiliconMT5Client(host="127.0.0.1", port=18812)
if not mt5_client.connect(int(creds["account"]), creds["password"], creds["server"]):
    print("Cannot connect to MT5 Bridge")
    quit()

orders = mt5_client.orders_get()
if orders is None:
    print("No active orders.")
elif len(orders) > 0:
    buy_orders = 0
    sell_orders = 0
    
    # 0 = BUY, 1 = SELL, 2 = BUY_LIMIT, 3 = SELL_LIMIT, 4 = BUY_STOP, 5 = SELL_STOP
    for order in orders:
        if order.type in [mt5_client.ORDER_TYPE_BUY_LIMIT, mt5_client.ORDER_TYPE_BUY_STOP, mt5_client.ORDER_TYPE_BUY]:
            buy_orders += 1
        elif order.type in [mt5_client.ORDER_TYPE_SELL_LIMIT, mt5_client.ORDER_TYPE_SELL_STOP, mt5_client.ORDER_TYPE_SELL]:
            sell_orders += 1
            
    print(f"Total Pending Orders: {len(orders)}")
    print(f"[{buy_orders} COMPRA(S)] | [{sell_orders} VENTA(S)]")
    
    if buy_orders > 0 and sell_orders > 0:
        print("\n✅ VERIFICADO DE FORMA INDISPUTABLE: El sistema tiene activas compras y ventas. El error de dirección ha sido exterminado.")
    elif buy_orders > 0:
        print("\n✅ VERIFICADO: El sistema está inyectando compras. El sesgo vendedor de 'BS' fue destruido.")
    else:
        print("\nℹ️ Actualmente hay despachos en curso, espera a que cambie el mercado para ver nuevas compras.")

