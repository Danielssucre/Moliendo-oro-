import sys
import os
PROJECT_ROOT = "/Users/danielsuarezsucre/TRADING/trading_agent"
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, "dashboard/backend"))

from app.services.mt5_service import MT5Service

service = MT5Service(PROJECT_ROOT)
if service.connect():
    print("Conectado a MT5!")
    orders = service.client.orders_get()
    
    if orders and len(orders) > 0:
        print(f"🗑️ Eliminando {len(orders)} órdenes...")
        deleted = 0
        for o in orders:
            req = {
                "action": service.client.TRADE_ACTION_REMOVE,
                "order": o.ticket
            }
            res = service.client.order_send(req)
            if res and res.retcode == service.client.TRADE_RETCODE_DONE:
                deleted += 1
        print(f"✅ Se eliminaron {deleted} órdenes pendientes.")
    else:
        print("🤷 No hay órdenes que borrar.")
else:
    print("❌ Falló la conexión.")
