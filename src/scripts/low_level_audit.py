#!/usr/bin/env python3
"""
low_level_audit.py — Silicon Bridge Low-Level Diagnostics (v4.7.0)
Tests pure latency, symbol visibility, and market session status.
"""
import sys
import os
import time
import json
from datetime import datetime

# Path setup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

RPYC_PORT = 18812

def audit():
    print("=" * 70)
    print("🔍 [PHASE 99] AUDITORÍA DE COMUNICACIÓN FÍSICA (WINE IPC)")
    print("=" * 70)

    # 1. TEST DE LATENCIA PURA
    try:
        from siliconmetatrader5 import MetaTrader5
        mt5 = MetaTrader5(port=RPYC_PORT)
        
        t0 = time.time()
        init_ok = mt5.initialize()
        t_init = (time.time() - t0) * 1000
        
        if not init_ok:
            print(f"❌ FALLO DE INICIALIZACIÓN: {mt5.last_error()}")
            return

        # Latencia simple: version() y terminal_info()
        t1 = time.time()
        version = mt5.version()
        t_ver = (time.time() - t1) * 1000
        
        t2 = time.time()
        t_info = mt5.terminal_info()
        t_info_lat = (time.time() - t2) * 1000
        
        print(f"✅ LATENCIA RPyC/Wine:")
        print(f"   - initialize():      {t_init:7.2f} ms")
        print(f"   - version():         {t_ver:7.2f} ms")
        print(f"   - terminal_info():   {t_info_lat:7.2f} ms")
        print(f"   - Versión MT5:       {version}")
        print(f"   - Broker Connected:  {'✅ SÍ' if t_info.connected else '❌ NO (Broker Offline)'}")
        # t_info no tiene 'server', omitimos para no crashear
        
    except Exception as e:
        print(f"❌ EXCEPCIÓN CRÍTICA EN PUENTE: {e}")
        return

    # 2. AUDITORÍA DE SYMBOL_SELECT (MARKET WATCH)
    print("\n📦 [MARKET WATCH] AUDITING SYMBOL VISIBILITY...")
    
    # Load Asset Map from Portfolio or local default
    try:
        portfolio_path = "config/portfolio.json"
        if os.path.exists(portfolio_path):
            with open(portfolio_path, 'r') as f:
                data = json.load(f)
                assets = data.get("assets", {})
        else:
            assets = {"EURUSD":"EURUSD", "GBPUSD":"GBPUSD", "USDJPY":"USDJPY", "SOLUSD":"SOLUSD"}
        
        invisible = []
        visible = []
        for pair, sym in assets.items():
            info = mt5.symbol_info(sym)
            if info is None:
                invisible.append(sym)
            elif not info.visible:
                invisible.append(sym)
            else:
                visible.append(sym)
        
        print(f"   - SÍMBOLOS VISIBLES:    {len(visible)}")
        print(f"   - SÍMBOLOS NO VISIBLES: {len(invisible)}")
        if invisible:
            print(f"   ⚠️  ADVERTENCIA: Los siguientes símbolos NO están en Market Watch: {invisible}")
            print(f"      (Esto causa timeouts ya que el terminal no tiene ticks en cache para ellos)")
            
    except Exception as e:
        print(f"❌ ERROR EN AUDITORÍA DE SÍMBOLOS: {e}")

    # 3. EL FACTOR MARKET CLOSED / ORDER CHECK
    print("\n🛡️ [ORDER CHECK] AUDITING MARKET STATUS (SATURDAY TEST)...")
    try:
        # Usamos SOLUSD como prueba ya que las cryptos suelen operar 24/7
        # Pero revisaremos un Major también para ver el contraste.
        test_syms = ["EURUSD", "SOLUSD"]
        
        for sym in test_syms:
            info = mt5.symbol_info(sym)
            if info is None:
                print(f"   - {sym:7}: Símbolo no encontrado en broker.")
                continue
            
            tick = mt5.symbol_info_tick(sym)
            if not tick:
                print(f"   - {sym:7}: ❌ Sin cotización (Tick es None). MERCADO CERRADO.")
                continue
            else:
                print(f"   - {sym:7}: 💰 Tick OK (Ask: {tick.ask})")

            # Intentar order_check
            check_req = {
                "action": int(mt5.TRADE_ACTION_DEAL),
                "symbol": str(sym),
                "volume": float(info.volume_min),
                "type": int(mt5.ORDER_TYPE_BUY),
                "price": float(tick.ask),
                "magic": 999111,
                "comment": "AUDIT_CHECK",
                "type_filling": int(info.filling_mode & 3) if info.filling_mode > 0 else 1
            }
            
            t_check = time.time()
            res = mt5.eval(f"mt5.order_check({repr(check_req)})")
            lat_check = (time.time() - t_check) * 1000
            
            if res is None:
                err = mt5.last_error()
                print(f"   - {sym:7}: ❌ order_check() -> None | Last Error: {err}")
            elif res.retcode == 0:
                print(f"   - {sym:7}: ✅ Mercado ABIERTO. Check OK ({lat_check:.2f} ms).")
            else:
                print(f"   - {sym:7}: ⚠️ Mercado CERRADO o Restringido ({res.comment}, retcode: {res.retcode}).")

    except Exception as e:
        print(f"❌ ERROR EN ORDER CHECK: {e}")

    print("\n" + "=" * 70)
    print("📊 DIAGNÓSTICO FINAL:")
    if t_info_lat > 500:
        print("🔴 CRÍTICO: El Silicon Bridge (Wine IPC) está LENTO (>500ms por comando básico).")
    else:
        print("🟢 SALUDABLE: Latencia de bajo nivel óptima. El timeout es por respuesta del Broker.")
    print("=" * 70)

if __name__ == "__main__":
    audit()
