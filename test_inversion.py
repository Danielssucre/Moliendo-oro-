import sys
import os

PROJECT_ROOT = "/Users/danielsuarezsucre/TRADING/trading_agent"
sys.path.append(PROJECT_ROOT)

from src.nanobot.strategies.mega_grid_v2 import MegaGridV2

print("==================================================")
print("🛡️ PRUEBA DE FUEGO: AUDITORÍA DEL INVERSION PIPELINE")
print("==================================================\n")

# Parámetros de la simulación del Arquitecto
pair = "EURUSD"
original_signal = 1  # 1 = BUY
entry_price = 1.1000
sl_dist_pips = 50
tp_dist_pips = 100
point = 0.0001
atr_simulado = 0.0050 # Equivalente a 50 pips si el multiplier es 1.0

print(f"📡 [SEÑAL ORIGINAL / NEM1]")
print(f"Activo: {pair} | Dirección: BUY (1) | Precio MT5 Local (Ask): {entry_price}")
print(f"Meta original: SL a 50 pips (1.0950) | TP a 100 pips (1.1100)\n")

print(f"🔄 INICIANDO MODO: NEM2 (Antithesis)...\n")

# Construyendo la configuración para MegaGrid
mock_config = {
    "num_levels": 1,
    "risk_distribution": [0.01],
    "rr_levels": [2.0], # 100 pips TP / 50 pips SL = 2.0 RR
    "distance_multiplier": 0,
    "sl_multiplier": 1.0, # 1.0 * atr_simulado = 50 pips
    "comment_prefix": "TEST_"
}

strategy = MegaGridV2.for_forex(**mock_config)

# Generación del Pool
# AQUÍ SE RESPONDE LA PREGUNTA DE LA BOMBA LÓGICA
# Se pasa direcction=original_signal (1)
levels = strategy.generate_pool(
    symbol=pair, 
    entry_price=entry_price, 
    atr=atr_simulado,
    direction=original_signal, 
    total_risk=0.01, 
    is_scout=False, 
    nem_type="NEM2"
)

# Simulamos la extracción en run_live.py
for level in levels:
    nem_side = level['side'] # ESTE DEBE SER -1 (SELL) PARA NEM2
    side_str = "BUY" if nem_side == 1 else "SELL"
    
    sl_dist = atr_simulado * level['sl_mult']
    tp_dist = sl_dist * level['rr']
    
    if nem_side == 1: # BUY
        sl_price = level['entry'] - sl_dist
        tp_price = level['entry'] + tp_dist
    else: # SELL
        sl_price = level['entry'] + sl_dist
        tp_price = level['entry'] - tp_dist
        
    print(f"🚀 [MEGAGRID DISPATCH]")
    print(f"Dirección final (side_str enviado a broker): {side_str}")
    print(f"Entry_price: {level['entry']:.5f}")
    print(f"SL_price: {sl_price:.5f}")
    print(f"TP_price: {tp_price:.5f}")
    
    if side_str == "SELL" and sl_price == 1.1050 and tp_price == 1.0900:
        print("\n✅ VICTORIA MATEMÁTICA: La matemática cuadra perfectamente para una VENTA. Los Stops son Válidos para MT5 y no hay Bomba Lógica.")
    else:
        print("\n❌ FALLO DETECTADO: Los números no cuadran con una venta válida.")
