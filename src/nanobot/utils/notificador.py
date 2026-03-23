"""
Telegram notification manager for the trading agent.
"""
import requests
import logging
from typing import Dict, Any, Optional
from src.api.api_manager import api_manager
from src.nanobot.utils.telegram_bot import TelegramBot

logger = logging.getLogger(__name__)

class Notificador:
    """Handles sending notifications to Telegram with Throttling."""
    
    def __init__(self):
        self.bot = TelegramBot()
        self.enabled = self.bot.enabled
        self.last_update_id = 0
        if self.enabled:
            self._skip_old_messages()

    def enviar_mensaje(self, mensaje: str) -> bool:
        """Send a plain text message via the throttled bot."""
        if not self.enabled:
            return False
        return self.bot.send_message(mensaje)

    def enviar_alerta_sniper(self, signal_data: Dict[str, Any]) -> bool:
        """Send a formatted Sniper signal alert."""
        if not self.enabled:
            return False
            
        pair = signal_data.get('pair', 'UNKNOWN')
        direction = str(signal_data.get('direction', '')).upper()
        entry = signal_data.get('entry_price', 0.0)
        tp = signal_data.get('take_profit', 0.0)
        sl = signal_data.get('stop_loss', 0.0)
        prob = signal_data.get('probability', 0.0)
        
        emoji = "🚀" if direction == "BUY" else "🔻"
        
        mensaje = (
            f"{emoji} *NUEVA SEÑAL SNIPER: {pair}*\n\n"
            f"🔹 *Acción*: {direction}\n"
            f"🎯 *Entrada*: `{entry:.5f}`\n"
            f"✅ *Take Profit*: `{tp:.5f}`\n"
            f"❌ *Stop Loss*: `{sl:.5f}`\n\n"
            f"📊 *Probabilidad*: `{prob:.1%}`\n"
            f"💰 *Uso API*: `{getattr(api_manager, 'request_count', 0)}/800` (Hoy)\n\n"
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
