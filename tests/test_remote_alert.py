"""
Script to test remote notifications with budget info, simulating an off-schedule signal.
"""
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.notificador import Notificador
from src.api.api_manager import api_manager

def test_remote_alert():
    print("📡 Simulando señal fuera de horario...")
    notificador = Notificador()
    
    # Simular un conteo de API
    api_manager.request_count = 145
    
    # Datos de señal simulada
    test_signal = {
        "pair": "GBPUSD",
        "direction": "buy",
        "entry_price": 1.25430,
        "take_profit": 1.25850,
        "stop_loss": 1.25150,
        "probability": 0.825
    }
    
    print(f"Enviando alerta para {test_signal['pair']}...")
    exito = notificador.enviar_alerta_sniper(test_signal)
    
    if exito:
        print("✅ Alerta enviada con éxito. Revisa tu móvil.")
        print("💡 Verás el campo 'Uso API: 145/800'.")
    else:
        print("❌ Error al enviar la alerta.")

if __name__ == "__main__":
    test_remote_alert()
