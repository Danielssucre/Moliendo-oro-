import os
import sys
import json
import time

# Sync path to import siliconmetatrader5 if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from siliconmetatrader5 import MetaTrader5
except ImportError:
    print("❌ siliconmetatrader5 not found. Cannot proceed with manual purge on Mac.")
    sys.exit(1)

def manual_purge():
    client = MetaTrader5(port=18812) # Default port usually
    
    # Credentials from known fallback
    c_login = 1521200226
    c_pass = "Y9*VlN1c$9f*I?"
    c_server = "FTMO-Demo2"
    
    print(f"📡 CONECTANDO PARA PURGA MANUAL: {c_server} (#{c_login})...")
    
    if not client.initialize(login=c_login, password=c_pass, server=c_server):
        print(f"❌ Fallo al conectar: {client.last_error()}")
        return

    # 1. CANCELAR PENDIENTES
    orders = client.orders_get()
    if orders:
        print(f"🧹 Detectadas {len(orders)} órdenes pendientes. Cancelando...")
        for o in orders:
            req = {"action": client.TRADE_ACTION_REMOVE, "order": o.ticket}
            client.order_send(req)
            print(f"✅ Cancelada #{o.ticket}")

    # 2. CERRAR POSICIONES
    positions = client.positions_get()
    if positions:
        print(f"🔥 Detectadas {len(positions)} posiciones abiertas. Cerrando...")
        for p in positions:
            tick = client.symbol_info_tick(p.symbol)
            req = {
                "action": client.TRADE_ACTION_DEAL,
                "symbol": p.symbol,
                "volume": p.volume,
                "type": client.ORDER_TYPE_SELL if p.type == 0 else client.ORDER_TYPE_BUY,
                "position": p.ticket,
                "price": tick.bid if p.type == 0 else tick.ask,
                "type_filling": client.ORDER_FILLING_IOC,
            }
            client.order_send(req)
            print(f"✅ Cerrada #{p.ticket} ({p.symbol})")

    client.shutdown()
    print("✨ PURGA COMPLETADA.")

if __name__ == "__main__":
    manual_purge()
