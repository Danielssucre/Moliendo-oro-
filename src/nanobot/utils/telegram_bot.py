import requests
import json
import time
from nanobot.utils.logger import logger
from nanobot.utils.config import Config

class TelegramBot:
    def __init__(self):
        self.config = Config()
        self.enabled = False
        self.token = None
        self.chat_id = None
        self.last_sent_time = 0
        self.retry_after_until = 0
        self.last_throttle_log = 0
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
        """Send a message with throttling and fail-safe for Markdown errors."""
        if not self.enabled:
            return
        
        current_time = time.time()
        if current_time < self.retry_after_until:
            return

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
                
                # FAIL-SAFE: Si falla el parseo de Markdown, enviar en texto plano
                if response.status_code == 400 and "can't parse" in response.text:
                    logger.warning("⚠️ Telegram Markdown error. Re-trying as plain text.")
                    payload["parse_mode"] = ""
                    response = requests.post(url, json=payload, timeout=15)
                    return response.status_code == 200

                if response.status_code == 429:
                    retry_after = response.json().get("parameters", {}).get("retry_after", 30)
                    self.retry_after_until = time.time() + retry_after
                    return False
                    
            except Exception as e:
                logger.error(f"Telegram Send Error: {e}")
            
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
        
        risk_pct = (signal.get('risk_amount', 0.0) / signal.get('capital', 1.0)) * 100 if signal.get('capital', 0) > 0 else 0.0
        
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
            
            f"⚖️ *Risk Execution*\n"
            f"Lots: *{signal.get('lot_size', 0.0)}*\n"
            f"Risk: ${signal.get('risk_amount', 0.0):.2f} ({risk_pct:.2f}%)\n"
            f"Capital: ${signal.get('capital', 0.0):,.2f}\n\n"
            
            f"🔮 *Oracle Verification*\n"
            f"Status: {'✅ CONFIRMED' if signal.get('oracle_verified', True) else '⚠️ WARNING'}"
        )
        
        self.send_message(msg)
    def send_basket_report(self, reason: str, profit: float, initial_capital: float):
        """Send a specialized mission report for Basket Lock events."""
        if not self.enabled:
            return
            
        profit_pct = (profit / initial_capital) * 100 if initial_capital > 0 else 0.0
        
        msg = (
            f"🎯 *BASKET MISSION REPORT*\n"
            f"============================\n"
            f"Status: *CLOSED & SECURED* ✅\n\n"
            
            f"💰 *Gains:* `${profit:,.2f}`\n"
            f"📈 *Yield:* `{profit_pct:.2f}%` of day start\n"
            f"🏦 *Capital Ref:* `${initial_capital:,.2f}`\n\n"
            
            f"📝 *Reason:* `{reason}`\n\n"
            f"⚖️ *Action:* Bot has closed all positions and locked the dashboard for profit protection.\n"
            f"============================"
        )
        self.send_message(msg)

    def send_health_update(self, symbol: str, old_status: str, new_status: str, score: float):
        """Alert when an asset changes its Bayesian health status."""
        if not self.enabled:
            return
            
        emoji = "🛡️" if "Healthy" in new_status else "☢️"
        
        msg = (
            f"{emoji} *ASSET PURIFICATION ALERT*\n"
            f"Symbol: `{symbol}`\n"
            f"Transition: `{old_status}` ➡️ *{new_status}*\n"
            f"Bayesian Score ($S_{{hp}}$): `{score:.3f}`\n\n"
            f"System has automatically updated the operational mode for this asset."
        )
        self.send_message(msg)
