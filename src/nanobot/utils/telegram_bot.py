import requests
import json
import time
from src.nanobot.utils.logger import logger
from src.nanobot.utils.config import Config

class TelegramBot:
    def __init__(self):
        self.config = Config()
        self.enabled = False
        self.token = None
        self.chat_id = None
        self.last_sent_time = 0
        self.retry_after_until = 0
        self.min_delay = 1.5  # Seconds between messages
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
        """Send a plain text message with throttling."""
        if not self.enabled:
            return
        
        # Check if we are in a mandatory wait period from a previous 429
        current_time = time.time()
        if current_time < self.retry_after_until:
            wait_time = self.retry_after_until - current_time
            logger.warning(f"🚫 Telegram: Throttled. Waiting {wait_time:.1f}s more.")
            return

        # Enforce minimum delay between messages
        elapsed = current_time - self.last_sent_time
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        for attempt in range(2):
            try:
                response = requests.post(url, json=payload, timeout=15)
                self.last_sent_time = time.time()
                
                if response.status_code == 200:
                    return True
                
                if response.status_code == 429:
                    retry_after = response.json().get("parameters", {}).get("retry_after", 30)
                    self.retry_after_until = time.time() + retry_after
                    logger.error(f"❌ Telegram 429: Rate limited. Blocking for {retry_after}s.")
                    return False
                    
                logger.error(f"Telegram Send Error (Attempt {attempt+1}): {response.text}")
            except Exception as e:
                logger.error(f"Telegram Connection Error (Attempt {attempt+1}): {e}")
            
            time.sleep(self.min_delay)
        return False

    def send_signal(self, signal: dict):
        """Format and send a trading signal."""
        if not self.enabled:
            return
            
        # Format the message (Defensive Phase 8)
        direction = str(signal.get('direction', '')).upper()
        direction_emoji = "🟢" if direction == "BUY" else "🔴"
        pair = signal.get('pair', 'UNKNOWN')
        entry = signal.get('entry', 0.0)
        sl = signal.get('sl', 0.0)
        tp = signal.get('tp', 0.0)
        
        msg = (
            f"*{direction_emoji} SIGNAL: {pair}*\n"
            f"Strategy: {signal.get('strategy', 'Hybrid')}\n"
            f"Time: `{signal.get('timestamp', 'N/A')}`\n\n"
            
            f"*ENTRY: {entry:.5f}*\n"
            f"SL: `{sl:.5f}` ({signal.get('sl_pips', 0.0):.1f} pips)\n"
            f"TP: `{tp:.5f}`\n\n"
            
            f"📊 *Indicators*\n"
            f"ADX: `{signal.get('adx', 0.0):.1f}`\n"
            f"RSI: `{signal.get('rsi', 0.0):.1f}`\n"
            f"ATR: `{signal.get('atr', 0.0):.5f}`\n\n"
            
            f"💰 *Risk (Fixed 1%)*\n"
            f"Lots: *{signal.get('lot_size', 0.0)}*\n"
            f"Risk: ${signal.get('risk_amount', 0.0):.2f}\n"
            f"Capital: ${signal.get('capital', 0.0):,.2f}\n\n"
            
            f"🔮 *Oracle Verification*\n"
            f"Status: {'✅ CONFIRMED' if signal.get('oracle_verified') else '⚠️ WARNING'}"
        )
        
        self.send_message(msg)
