import sys
import os
import json
import logging
from unittest.mock import MagicMock

# Configurar rutas
BASE_DIR = "/Users/danielsuarezsucre/TRADING/trading_agent"
sys.path.append(os.path.join(BASE_DIR, "src"))

from nanobot.strategies.mega_grid_v2 import MegaGridV2

# Mock de objetos necesarios
class MockSignal:
    def __init__(self, symbol, direction, strategy_tag):
        self.symbol = symbol
        self.direction = direction # 1=BUY, -1=SELL
        self.strategy_tag = strategy_tag
        self.force_scout = False

def run_diagnostic():
    print("\n🧪 --- DIAGNÓSTICO DE POLARIDAD OMEGA+ ---")
    strategy = MegaGridV2()
    
    # CASO 1: SEÑAL BUY + NEM2 (Antítesis) -> Debería resultar en SELL
    print("\n🔹 ESCENARIO 1: Señal BUY (Original) | Rol: NEM2 (Antítesis)")
    pool_1 = strategy.generate_pool(
        symbol="BTCUSD", entry_price=65000, atr=500,
        direction=1, # BUY
        nem_type="NEM2"
    )
    side_1 = pool_1[0]['side']
    side_str_1 = "BUY" if side_1 == 1 else "SELL"
    print(f"📊 RESULTADO: Lado de la Red = {side_str_1} ({side_1})")
    if side_1 == -1: print("✅ CERTIFICADO: Inversión Correcta.")
    else: print("❌ FALLO: Debería ser SELL.")

    # CASO 2: SEÑAL SELL + NEM2 (Antítesis) -> Debería resultar en BUY
    print("\n🔹 ESCENARIO 2: Señal SELL (Original) | Rol: NEM2 (Antítesis)")
    pool_2 = strategy.generate_pool(
        symbol="BTCUSD", entry_price=65000, atr=500,
        direction=-1, # SELL
        nem_type="NEM2"
    )
    side_2 = pool_2[0]['side']
    side_str_2 = "BUY" if side_2 == 1 else "SELL"
    print(f"📊 RESULTADO: Lado de la Red = {side_str_2} ({side_2})")
    if side_2 == 1: print("✅ CERTIFICADO: Inversión Correcta.")
    else: print("❌ FALLO: Debería ser BUY.")

    # CASO 3: SEÑAL BUY + NEM1 (Trend) -> Debería resultar en BUY
    print("\n🔹 ESCENARIO 3: Señal BUY (Original) | Rol: NEM1 (Trend)")
    pool_3 = strategy.generate_pool(
        symbol="BTCUSD", entry_price=65000, atr=500,
        direction=1, # BUY
        nem_type="NEM1"
    )
    side_3 = pool_3[0]['side']
    side_str_3 = "BUY" if side_3 == 1 else "SELL"
    print(f"📊 RESULTADO: Lado de la Red = {side_str_3} ({side_3})")
    if side_3 == 1: print("✅ CERTIFICADO: Tendencia Correcta.")
    else: print("❌ FALLO: Debería ser BUY.")

if __name__ == "__main__":
    run_diagnostic()
