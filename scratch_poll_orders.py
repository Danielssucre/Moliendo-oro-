import sys, os, time, json
PROJECT_ROOT = "/Users/danielsuarezsucre/TRADING/trading_agent"
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, "dashboard/backend"))
from app.services.mt5_service import MT5Service

service = MT5Service(PROJECT_ROOT)
if not service.connect(): quit()

orders = service.client.orders_get()
buys = 0
sells = 0
if orders:
    for o in orders:
        if o.type in [service.client.ORDER_TYPE_BUY, service.client.ORDER_TYPE_BUY_LIMIT, service.client.ORDER_TYPE_BUY_STOP]: buys += 1
        elif o.type in [service.client.ORDER_TYPE_SELL, service.client.ORDER_TYPE_SELL_LIMIT, service.client.ORDER_TYPE_SELL_STOP]: sells += 1

print(f"[{buys} BUYS PENDIENTES] | [{sells} SELLS PENDIENTES] | Total: {buys+sells}")
