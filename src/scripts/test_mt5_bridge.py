#!/usr/bin/env python3
"""
test_mt5_bridge.py — Silicon Bridge Stress Test (v4.6.0)
Coloca una orden SCOUT de 0.01 en GBPUSD ignorando el Dashboard
para confirmar si el problema es de MT5 o de la lógica del bot.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RPYC_PORT = 18812

def run_test():
    print("=" * 60)
    print("🔬 SILICON BRIDGE STRESS TEST — v4.6.0")
    print("=" * 60)

    # --- 1. Conectar al Puente Silicon ---
    try:
        from siliconmetatrader5 import MetaTrader5
        mt5 = MetaTrader5(port=RPYC_PORT)
        print(f"✅ [1/5] Conexión RPyC establecida en localhost:{RPYC_PORT}")
    except Exception as e:
        print(f"❌ [1/5] FALLO DE CONEXIÓN RPYC: {e}")
        print("→ Verifica que start_dashboard.sh haya iniciado el puente RPyC.")
        return

    # --- 2. Inicializar Terminal ---
    try:
        if not mt5.initialize():
            print(f"❌ [2/5] mt5.initialize() falló: {mt5.last_error()}")
            return
        print("✅ [2/5] Terminal MT5 inicializada.")
    except Exception as e:
        print(f"❌ [2/5] Excepción en initialize(): {e}")
        return

    # --- 3. Verificar Estado del Terminal ---
    try:
        term = mt5.terminal_info()
        acc = mt5.account_info()
        if not term or not acc:
            print("❌ [3/5] terminal_info() o account_info() devolvió None.")
            print("→ El terminal puede estar abierto pero sin sesión activa.")
            return
        print(f"✅ [3/5] Terminal OK | Cuenta: #{acc.login} | Balance: ${acc.balance:,.2f}")
        print(f"   AlgoTrading: {'✅ HABILITADO' if term.trade_allowed else '❌ DESHABILITADO'}")
        if not term.trade_allowed:
            print("\n⛔ DIAGNÓSTICO: Habilita 'Algo Trading' en MT5 y vuelve a correr este test.")
            return
    except Exception as e:
        print(f"❌ [3/5] Error verificando estado: {e}")
        return

    # --- 4. Obtener Tick de GBPUSD ---
    try:
        mt5.symbol_select("GBPUSD", True)
        time.sleep(0.2)
        tick = mt5.symbol_info_tick("GBPUSD")
        info = mt5.symbol_info("GBPUSD")
        if not tick or not info:
            print("❌ [4/5] No se pudo obtener cotización de GBPUSD.")
            return
        
        # Modo de llenado correcto
        filling_type = int(info.filling_mode)
        if filling_type == 0: filling_type = 1  # Fallback IOC
        
        print(f"✅ [4/5] GBPUSD — Ask: {tick.ask:.5f} | Bid: {tick.bid:.5f} | Filling: {filling_type}")
    except Exception as e:
        print(f"❌ [4/5] Error obteniendo tick: {e}")
        return

    # --- 5. Enviar Orden SCOUT 0.01 (Todos los valores como tipos nativos) ---
    print("\n📤 [5/5] Enviando orden SCOUT de prueba (0.01 lot)...")
    try:
        request = {
            "action": int(mt5.TRADE_ACTION_DEAL),
            "symbol": "GBPUSD",
            "volume": 0.01,
            "type": int(mt5.ORDER_TYPE_BUY),
            "price": float(tick.ask),
            "deviation": 20,
            "magic": 999888,
            "comment": "BRIDGE_STRESS_TEST",
            "type_time": int(mt5.ORDER_TIME_GTC),
            "type_filling": filling_type,
        }
        
        t_start = time.time()
        result = mt5.order_send(request)
        latency = (time.time() - t_start) * 1000
        
        if result is None:
            print(f"❌ [5/5] order_send() devolvió None (latencia: {latency:.0f}ms)")
            print("→ CAUSA: El puente RPyC no respondió o el tipo de datos era inválido.")
            print("→ Última error MT5:", mt5.last_error())
        elif result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"✅ [5/5] ORDEN COLOCADA EXITOSAMENTE (latencia: {latency:.0f}ms)")
            print(f"   Ticket: #{result.order} | Precio: {result.price:.5f}")
            print("\n🟢 DIAGNÓSTICO: El Puente Silicon está OPERATIVO. El problema era de lógica interna.")
        else:
            print(f"⚠️  [5/5] Orden rechazada: {result.comment} (retcode: {result.retcode}) | latencia: {latency:.0f}ms")
            
            known = {
                10027: "AutoTrading deshabilitado por el cliente",
                10044: "Solo cierre de posiciones permitido",
                10015: "Precio inválido — usa ORDER_TYPE_DEAL con precio actual",
                10030: "Tipo de filling inválido para este símbolo",
                10018: "Mercado cerrado",
            }
            if result.retcode in known:
                print(f"   → {known[result.retcode]}")

    except Exception as e:
        print(f"❌ [5/5] Excepción al enviar orden: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    run_test()
