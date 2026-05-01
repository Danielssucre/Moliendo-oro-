import os
import sys
import json
from siliconmetatrader5 import MetaTrader5

def list_all():
    client = MetaTrader5(port=18812)
    # FTMO Demo Account from config
    c_login = 1513194377
    c_server = "FTMO-Demo"
    # Note: password is empty in config, but maybe bridge handles it or it works without it if already logged in.
    
    if not client.initialize(login=c_login, server=c_server):
        print(f"❌ Fallo al conectar: {client.last_error()}")
        return

    orders = client.orders_get()
    print(f"--- PENDING ORDERS ({len(orders) if orders else 0}) ---")
    if orders:
        for o in orders:
            print(f"#{o.ticket} | {o.symbol} | {o.type} | Comment: {o.comment}")

    positions = client.positions_get()
    print(f"--- OPEN POSITIONS ({len(positions) if positions else 0}) ---")
    if positions:
        for p in positions:
            print(f"#{p.ticket} | {p.symbol} | {p.type} | Comment: {p.comment}")

    client.shutdown()

if __name__ == "__main__":
    list_all()
