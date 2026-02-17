"""
BrainHandler - Conversational intelligence for the trading agent.
Connects to Google Gemini API to provide natural language responses.
"""
import google.generativeai as genai
from typing import Optional
from src.nanobot.utils.config import config
from src.nanobot.utils.logger import logger

class BrainHandler:
    """Handles natural language interaction using Gemini."""
    
    def __init__(self):
        self.gemini_config = config.get_api_config("gemini")
        self.api_key = self.gemini_config.get("api_key")
        self.model_name = self.gemini_config.get("model", "gemini-1.5-flash")
        
        self.enabled = self._validate_config()
        if self.enabled:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=(
                    "Eres Alpha, un asistente experto en trading cuantitativo y análisis técnico. "
                    "Tu propósito es ayudar al usuario a entender el mercado, analizar pares y gestionar su portafolio. "
                    "Habla de forma profesional, clara y directa. Usa emojis de vez en cuando para una mejor experiencia móvil. "
                    "Si el usuario te pregunta algo sobre trading, da respuestas basadas en análisis técnico y gestión de riesgo. "
                    "No des consejos financieros directos, siempre recuerda la gestión de riesgo. "
                    "Conoces el sistema 'Sniper Strategy' que usa este bot, basado en multi-timeframe alignment, "
                    "Kalman filters y Monte Carlo simulations."
                )
            )
            self.chat = self.model.start_chat(history=[])
            logger.info(f"🧠 BrainHandler activado con modelo: {self.model_name}")
        else:
            logger.warning("🧠 BrainHandler desactivado (API Key faltante)")

    def _validate_config(self) -> bool:
        """Check if Gemini is properly configured."""
        if not self.api_key or "YOUR_GEMINI_API_KEY" in self.api_key:
            return False
        return True

    def procesar_lenguaje_natural(self, mensaje: str) -> str:
        """Process a natural language message and return AI response."""
        if not self.enabled:
            return (
                "⚠️ *Módulo de Conversación Desactivado*\n\n"
                "Para hablar conmigo, necesito que configures mi 'Cerebro' en `config/api_keys.json`. "
                "Necesitas una Gemini API Key de [AI Studio](https://aistudio.google.com/)."
            )
            
        try:
            logger.info(f"🧠 Brain: Procesando mensaje: {mensaje}")
            response = self.chat.send_message(mensaje)
            return response.text
        except Exception as e:
            logger.error(f"Error en BrainHandler: {e}")
            return f"❌ Ups, tuve un pequeño corto circuito mental: {str(e)}"

# Singleton-like access
brain_handler = BrainHandler()
