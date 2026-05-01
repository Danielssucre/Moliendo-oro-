import sys
import json
import time

PROJECT_ROOT = "/Users/danielsuarezsucre/TRADING/trading_agent"
sys.path.append(PROJECT_ROOT)
from src.nanobot.exchanges.mt5_client import SiliconMT5Client

creds_path = f"{PROJECT_ROOT}/config/credentials.json"
with open(creds_path, 'r') as f:
    creds = json.load(f).get("mt5", {})

client = SiliconMT5Client(host="127.0.0.1", port=18812)
if client.connect(int(creds["account"]), creds["password"], creds["server"]):
    orders = client.orders_get()
    
    if orders and len(orders) > 0:
        print(f"🗑️ Eliminando {len(orders)} órdenes fantasmas (antiguos SELLs)...")
        deleted = 0
        for o in orders:
            # Send delete request
            req = {
                "action": client.TRADE_ACTION_REMOVE,
                "order": o.ticket
            }
            res = client.order_send(req)
            if res and res.retcode == client.TRADE_RETCODE_DONE:
                deleted += 1
        print(f"✅ Se eliminaron {deleted} órdenes pendientes con éxito.")
    else:
        print("🤷 No se encontraron órdenes pendientes antiguas para borrar.")
else:
    print("❌ No se pudo conectar vía RPyC")
