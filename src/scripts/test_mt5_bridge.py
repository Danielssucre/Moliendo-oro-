#!/usr/bin/env python3
"""
test_mt5_bridge.py — Silicon Bridge Stress Test (v4.6.1)
Prueba el puente Silicon con SOLUSD (crypto) para confirmar
si el problema es de MT5 o de la lógica interna del bot.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RPYC_PORT  = 18812
TEST_SYMBOL = "SOLUSD"  # Cambia aquí para probar otros símbolos

# ─── Conversión de bitmask a enum de filling ────────────────────────────────
# info.filling_mode es un BITMASK (no el enum directo):
#   bit 0 → FOK   (ORDER_FILLING_FOK   = 0)
#   bit 1 → IOC   (ORDER_FILLING_IOC   = 1)
#   bit 2 → RETURN (ORDER_FILLING_RETURN = 2)
def resolve_filling(filling_mask: int) -> int:
    if filling_mask & 1:   return 0  # FOK
    if filling_mask & 2:   return 1  # IOC
    return 2                          # RETURN (fallback)


def run_test():
    print("=" * 60)
    print(f"🔬 SILICON BRIDGE STRESS TEST — v4.6.1  [{TEST_SYMBOL}]")
    print("=" * 60)

    # ── 1. Conectar al Puente RPyC ──────────────────────────────────────────
    try:
        from siliconmetatrader5 import MetaTrader5
        mt5 = MetaTrader5(port=RPYC_PORT)
        print(f"✅ [1/5] Conexión RPyC establecida en localhost:{RPYC_PORT}")
    except Exception as e:
        print(f"❌ [1/5] FALLO DE CONEXIÓN RPYC: {e}")
        print("→ Verifica que start_dashboard.sh haya iniciado el puente RPyC.")
        return

    # ── 2. Inicializar Terminal ─────────────────────────────────────────────
    try:
        if not mt5.initialize():
            print(f"❌ [2/5] mt5.initialize() falló: {mt5.last_error()}")
            return
        print("✅ [2/5] Terminal MT5 inicializada.")
    except Exception as e:
        print(f"❌ [2/5] Excepción en initialize(): {e}")
        return

    # ── 3. Verificar Estado del Terminal ───────────────────────────────────
    try:
        term = mt5.terminal_info()
        acc  = mt5.account_info()
        if not term or not acc:
            print("❌ [3/5] terminal_info() o account_info() devolvió None.")
            return
        print(f"✅ [3/5] Terminal OK | Cuenta: #{acc.login} | Balance: ${acc.balance:,.2f}")
        print(f"   AlgoTrading: {'✅ HABILITADO' if term.trade_allowed else '❌ DESHABILITADO'}")
        if not term.trade_allowed:
            print("\n⛔ DIAGNÓSTICO: Habilita 'Algo Trading' en MT5 y repite el test.")
            return
    except Exception as e:
        print(f"❌ [3/5] Error verificando estado: {e}")
        return

    # ── 4. Obtener Tick y resolving de Filling ─────────────────────────────
    try:
        mt5.symbol_select(TEST_SYMBOL, True)
        time.sleep(0.3)
        tick = mt5.symbol_info_tick(TEST_SYMBOL)
        info = mt5.symbol_info(TEST_SYMBOL)
        if not tick or not info:
            print(f"❌ [4/5] No se pudo obtener cotización de {TEST_SYMBOL}.")
            print("   → El símbolo puede no estar disponible en este broker/cuenta.")
            return

        filling_mask  = int(info.filling_mode)  # bitmask crudo
        filling_enum  = resolve_filling(filling_mask)  # enum correcto

        print(f"✅ [4/5] {TEST_SYMBOL}")
        print(f"   Ask: {tick.ask:.5f} | Bid: {tick.bid:.5f}")
        print(f"   filling_mode (mask): {filling_mask}  →  filling enum a usar: {filling_enum}")
        print(f"   Spread: {(tick.ask - tick.bid) / info.point:.1f} pts "
              f"| Min lot: {info.volume_min} | Step: {info.volume_step}")
    except Exception as e:
        print(f"❌ [4/5] Error obteniendo tick: {e}")
        return

    # ── 5. Enviar Orden SCOUT (todos los valores como nativos Python) ───────
    print(f"\n📤 [5/5] Enviando orden SCOUT BUY 0.01 en {TEST_SYMBOL}...")
    try:
        request = {
            "action":       int(mt5.TRADE_ACTION_DEAL),
            "symbol":       str(TEST_SYMBOL),
            "volume":       float(info.volume_min),   # lote mínimo del símbolo
            "type":         int(mt5.ORDER_TYPE_BUY),
            "price":        float(tick.ask),
            "deviation":    20,
            "magic":        999888,
            "comment":      "BRIDGE_STRESS_TEST_SOL",
            "type_time":    int(mt5.ORDER_TIME_GTC),
            "type_filling": filling_enum,
        }

        t0     = time.time()
        result = mt5.order_send(request)
        latency_ms = (time.time() - t0) * 1000

        if result is None:
            print(f"❌ [5/5] order_send() devolvió None (latencia: {latency_ms:.0f}ms)")
            print("   Última error MT5:", mt5.last_error())
            print("\n🔴 DIAGNÓSTICO: El Puente Silicon sigue fallando. Revisar Wine/RPyC.")

        elif result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"✅ [5/5] ¡ORDEN COLOCADA EXITOSAMENTE! (latencia: {latency_ms:.0f}ms)")
            print(f"   Ticket: #{result.order} | Precio: {result.price:.5f}")
            print("\n🟢 DIAGNÓSTICO: Puente Silicon OPERATIVO — {TEST_SYMBOL} ejecuta sin problemas.")

        else:
            known = {
                10004: "Requote — precio cambió, reintentar",
                10006: "Rechazada por el broker",
                10015: "Precio inválido — usa precio actual del tick",
                10017: "Trading deshabilitado para este símbolo",
                10018: "Mercado cerrado",
                10019: "Fondos insuficientes",
                10027: "AutoTrading deshabilitado por el cliente",
                10030: "Filling mode no soportado — bitmask mal interpretado",
                10044: "Solo cierre de posiciones permitido (CLOSE ONLY)",
            }
            desc = known.get(result.retcode, "Error desconocido")
            print(f"⚠️  [5/5] Orden rechazada | retcode: {result.retcode} | latencia: {latency_ms:.0f}ms")
            print(f"   Mensaje broker: '{result.comment}'")
            print(f"   → {desc}")

            if result.retcode == 10030:
                print("\n🔧 REMEDIO: Intenta forzar filling_enum=2 (RETURN) para este símbolo.")
                print("   Ajustando y re-intentando...")
                request["type_filling"] = 2
                result2 = mt5.order_send(request)
                if result2 and result2.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"✅ ¡Re-intento exitoso con RETURN filling! Ticket: #{result2.order}")
                elif result2:
                    print(f"⚠️  Re-intento también falló: {result2.comment} ({result2.retcode})")
                else:
                    print("❌ Re-intento devolvió None.")

    except Exception as e:
        print(f"❌ [5/5] Excepción al enviar orden: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    run_test()
