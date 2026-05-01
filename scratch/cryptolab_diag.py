import MetaTrader5 as mt5
import pandas as pd
import logging
import sys
import os

# Configurar logs básicos
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CryptoLab.Diag")

# Añadir path para importar nanobot
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "src"))

from src.nanobot.strategies.strategy_hub import StrategyHub

def diagnostic_cryptolab():
    if not mt5.initialize():
        print("❌ MT5 Init failed")
        return

    hub = StrategyHub()
    symbol = "BTCUSD"
    
    # Obtener datos M15
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 200)
    if rates is None or len(rates) == 0:
        print(f"❌ No se pudieron obtener datos para {symbol}")
        mt5.shutdown()
        return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    print(f"\n--- DIAGNÓSTICO CRYPTOLAB para {symbol} ---")
    
    # Probar señales en ambos modos
    modes = ["N1", "N2"]
    for m in modes:
        result = hub.get_signal(symbol, df, mode=m)
        print(f"MODO {m}: Signal={result.signal} | Strategy={result.strategy} | Source={result.source}")
        if result.metadata:
            print(f"   Metadata: {result.metadata}")

    mt5.shutdown()

if __name__ == "__main__":
    diagnostic_cryptolab()
