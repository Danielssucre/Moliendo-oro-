import requests
import json
from src.nanobot.utils.logger import logger
from src.nanobot.utils.config import Config

class TelegramBot:
    def __init__(self):
        self.config = Config()
        self.enabled = False
        self.token = None
        self.chat_id = None
        self._setup()
        
    def _setup(self):
        """Load credentials from config."""
        tg_conf = self.config.api_keys.get("telegram", {})
        self.token = tg_conf.get("bot_token")
        self.chat_id = tg_conf.get("chat_id")
        
        if self.token and self.chat_id:
            self.enabled = True
            logger.info("✅ Telegram Bot Configured.")
        else:
            logger.warning("⚠️ Telegram credentials missing in api_keys.json. Notifications disabled.")
            
    def send_message(self, message: str):
        """Send a plain text message."""
        if not self.enabled:
            return
        
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        for attempt in range(3):
            try:
                response = requests.post(url, json=payload, timeout=30)
                if response.status_code == 200:
                    break
                logger.error(f"Telegram Send Error (Attempt {attempt+1}): {response.text}")
            except Exception as e:
                logger.error(f"Telegram Connection Error (Attempt {attempt+1}): {e}")
            time.sleep(2)

    def send_signal(self, signal: dict):
        """Format and send a trading signal."""
        if not self.enabled:
            return
            
        # Format the message
        direction_emoji = "🟢" if signal['direction'] == "BUY" else "🔴"
        
        msg = (
            f"*{direction_emoji} SIGNAL: {signal['pair']}*\n"
            f"Strategy: {signal.get('strategy', 'Hybrid')}\n"
            f"Time: `{signal['timestamp']}`\n\n"
            
            f"*ENTRY: {signal['entry']:.5f}*\n"
            f"SL: `{signal['sl']:.5f}` ({signal['sl_pips']:.1f} pips)\n"
            f"TP: `{signal['tp']:.5f}`\n\n"
            
            f"📊 *Indicators*\n"
            f"ADX: `{signal.get('adx', 0):.1f}`\n"
            f"RSI: `{signal.get('rsi', 0):.1f}`\n"
            f"ATR: `{signal.get('atr', 0):.5f}`\n\n"
            
            f"💰 *Risk (Fixed 1%)*\n"
            f"Lots: *{signal.get('lot_size', 0.0)}*\n"
            f"Risk: ${signal.get('risk_amount', 0):.2f}\n"
            f"Capital: ${signal.get('capital', 0):,.2f}\n\n"
            
            f"🔮 *Oracle Verification*\n"
            f"Status: {'✅ CONFIRMED' if signal.get('oracle_verified') else '⚠️ WARNING'}"
        )
        
        self.send_message(msg)
