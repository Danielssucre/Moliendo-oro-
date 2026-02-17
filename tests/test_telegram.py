"""
Simple script to test Telegram notifications.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.notificador import Notificador
from src.utils.logger import logger

def test_telegram():
    print("🧪 Probando conexión con Telegram...")
    notificador = Notificador()
    
    if not notificador.enabled:
        print("❌ Error: Telegram no está configurado en config/api_keys.json")
        return

    # Mensaje de prueba sencillo
    exito = notificador.enviar_mensaje("🤖 Test de Conexion: ¡Hola! Tu bot de trading esta listo para enviarte señales.")
    
    if exito:
        print("✅ Mensaje enviado con éxito. Revisa tu móvil.")
    else:
        print("❌ Fallo el envío. Revisa el token y el chat_id.")

if __name__ == "__main__":
    test_telegram()
