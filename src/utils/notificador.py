"""
Telegram notification manager for the trading agent.
"""
import requests
import logging
from typing import Dict, Any, Optional
from src.api.api_manager import api_manager
from src.utils.config import config

logger = logging.getLogger(__name__)

class Notificador:
    """Handles sending notifications to Telegram."""
    
    def __init__(self):
        self.telegram_config = config.get_api_config("telegram")
        self.bot_token = self.telegram_config.get("bot_token")
        self.chat_id = self.telegram_config.get("chat_id")
        self.last_update_id = 0
        self.enabled = self._validate_config()
        if self.enabled:
            self._skip_old_messages()
        
    def _validate_config(self) -> bool:
        """Check if Telegram is properly configured."""
        if not self.bot_token or "YOUR_" in self.bot_token:
            logger.warning("Telegram Bot Token not configured. Notifications disabled.")
            return False
        if not self.chat_id or "YOUR_" in self.chat_id:
            logger.warning("Telegram Chat ID not configured. Notifications disabled.")
            return False
        return True

    def _skip_old_messages(self):
        """Skip messages already in the queue to start fresh."""
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        try:
            response = requests.get(url, params={"limit": 1, "offset": -1}, timeout=5)
            updates = response.json().get("result", [])
            if updates:
                self.last_update_id = updates[0]["update_id"]
                logger.info(f"✅ Telegram Link: Listo. Saltando hasta ID {self.last_update_id}")
        except Exception as e:
            logger.warning(f"⚠️ Telegram Link: No se pudo limpiar la cola: {e}")

    def enviar_mensaje(self, mensaje: str) -> bool:
        """Send a plain text message to Telegram."""
        if not self.enabled:
            return False
            
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": mensaje,
            "parse_mode": "Markdown"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info("Notificación enviada con éxito a Telegram.")
            return True
        except Exception as e:
            logger.error(f"Error enviando notificación a Telegram: {e}")
            return False

    def enviar_alerta_sniper(self, signal_data: Dict[str, Any]) -> bool:
        """Send a formatted Sniper signal alert."""
        if not self.enabled:
            return False
            
        pair = signal_data.get('pair')
        direction = signal_data.get('direction', '').upper()
        entry = signal_data.get('entry_price')
        tp = signal_data.get('take_profit')
        sl = signal_data.get('stop_loss')
        prob = signal_data.get('probability', 0)
        
        emoji = "🚀" if direction == "BUY" else "🔻"
        
        mensaje = (
            f"{emoji} *NUEVA SEÑAL SNIPER: {pair}*\n\n"
            f"🔹 *Acción*: {direction}\n"
            f"🎯 *Entrada*: `{entry:.5f}`\n"
            f"✅ *Take Profit*: `{tp:.5f}`\n"
            f"❌ *Stop Loss*: `{sl:.5f}`\n\n"
            f"📊 *Probabilidad*: `{prob:.1%}`\n"
            f"💰 *Uso API*: `{api_manager.request_count}/800` (Hoy)\n\n"
            f"💡 _Recuerda operar con gestión de riesgo._"
        )
        
        return self.enviar_mensaje(mensaje)

    def obtener_comandos(self) -> list:
        """Get pending commands from Telegram."""
        if not self.enabled:
            return []
            
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        params = {"offset": self.last_update_id + 1, "timeout": 0}
        
        try:
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            updates = response.json().get("result", [])
            if updates:
                logger.debug(f"Telegram: {len(updates)} nuevas actualizaciones.")
            
            commands = []
            for update in updates:
                self.last_update_id = update["update_id"]
                message = update.get("message") or update.get("edited_message", {})
                chat_id = str(message.get("chat", {}).get("id", ""))
                text = message.get("text", "")
                
                # Debug logging for every message received
                if text:
                    logger.debug(f"MSJ Recibido | Chat: {chat_id} | Text: {text}")

                # Only process commands from the authorized user
                if str(chat_id) == str(self.chat_id) and text.startswith("/"):
                    logger.info(f"📥 Comando remoto autorizado: {text}")
                    commands.append({
                        "text": text,
                        "chat_id": chat_id
                    })
            return commands
        except Exception as e:
            # Don't log spam as error, just debug
            logger.debug(f"Error obteniendo comandos de Telegram: {e}")
            return []
