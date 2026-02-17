"""
Processor for remote Telegram commands.
"""
import logging
from typing import Dict, Any, Optional
from src.api.api_manager import api_manager
from src.nanobot.utils.config import config
from src.nanobot.utils.brain_handler import brain_handler
from src.nanobot.utils.logger import logger

class CommandHandler:
    """Handles logic for remote commands received via Telegram."""
    
    def __init__(self, agent, capital_manager=None):
        self.agent = agent
        self.capital_manager = capital_manager
        
    def procesar_comando(self, comando: str) -> str:
        """Process a command and return the response text."""
        parts = comando.split()
        if not parts:
            return ""
            
        cmd = parts[0].lower()
        
        if cmd == "/start":
            return "¡Hola! Soy tu asistente de trading. Usa /help para ver los comandos disponibles."
            
        elif cmd == "/perfil":
            active = config.trading.get("active_profile", "unknown")
            profiles = config.trading.get("profiles", {})
            name = profiles.get(active, {}).get("name", active)
            
            if len(parts) > 1:
                new_profile = parts[1]
                if new_profile in profiles:
                    # Logic to switch would go here if we had a handler for config updates
                    return f"🔄 Para cambiar a `{new_profile}`, cámbialo en el menú principal del bot en la PC."
                return f"❌ Perfil `{new_profile}` no encontrado. Disponibles: {', '.join(profiles.keys())}"
                
            return f"⚙️ Estrategia activa: *{name}* (`{active}`)\nUsa `/help` para ver más."
            
        elif cmd == "/help":
            return (
                "🤖 *Comandos de Alpha*:\n\n"
                "🔹 `/status`: Estado del escáner y presupuesto\n"
                "🔹 `/analiza [PAR]`: Análisis Sniper inmediato\n"
                "🔹 `/perfil`: Ver perfiles dinámicos (Sniper, Scalper, Tokyo Daybreak)\n"
                "🔹 `/stats`: Rendimiento de la sesión\n"
                "🔹 `/abiertas`: Ver operaciones activas\n"
                "🔹 `/registrar [PERFIL] [PAR]`: Registrar trade desde señal\n"
                "🔹 `/help`: Esta ayuda"
            )
            
        elif cmd == "/status":
            req_count = api_manager.request_count
            return (
                f"✅ *Estado*: El escáner esta activo y vigilando el Golden Trio.\n"
                f"💰 *Presupuesto API*: `{req_count}/800` solicitudes hoy."
            )
            
        elif cmd == "/analiza":
            portfolio_pairs = ["AUDUSD", "GBPUSD", "USDCAD"]
            
            if len(parts) < 2:
                # Show Menu
                menu = "🎯 *MENÚ DE ANÁLISIS DUAL*\n"
                menu += "Selecciona un par o el portafolio completo:\n\n"
                for i, pair in enumerate(portfolio_pairs, 1):
                    menu += f"{i}. *{pair}*\n"
                menu += f"{len(portfolio_pairs)+1}. 📂 *PORTAFOLIO GOLDEN TRIO*\n\n"
                menu += "💡 Responde con `/analiza [Número]` o `/analiza [PAR]`"
                return menu
            
            input_val = parts[1].upper()
            
            # Handle numeric selection
            if input_val.isdigit():
                idx = int(input_val) - 1
                if 0 <= idx < len(portfolio_pairs):
                    return self._ejecutar_analisis_remoto(portfolio_pairs[idx])
                elif idx == len(portfolio_pairs):
                    # Portfolio analysis
                    return self._ejecutar_analisis_portafolio(portfolio_pairs)
                else:
                    return f"❌ Opción `{input_val}` no válida. Usa del 1 al {len(portfolio_pairs)+1}."
            
            if input_val == "PORTAFOLIO":
                return self._ejecutar_analisis_portafolio(portfolio_pairs)
                
            return self._ejecutar_analisis_remoto(input_val)
            
        elif cmd == "/stats":
            if self.capital_manager:
                cap = self.capital_manager.current_capital
                return f"📈 *Estadísticas de Sesión*:\n\n🔹 Capital Actual: `${cap:,.2f}`"
            return "❌ Información de capital no vinculada al bot."

        elif cmd == "/abiertas":
            trades = self.agent.trade_tracker.get_open_trades()
            if not trades:
                return "📂 *No hay operaciones abiertas.*"
            
            res = "📊 *OPERACIONES ACTIVAS*:\n\n"
            for t in trades:
                res += f"🔹 {t['pair']} ({t['direction']})\n   └ E: `{t['entry_price']}` | TP: `{t['take_profit']}` | SL: `{t['stop_loss']}`\n"
            return res

        elif cmd == "/registrar":
            # Simple registration from last signal or manual
            # For simplicity, we expect /registrar PAR para registrar el ultimo analisis
            if len(parts) < 2:
                return "❌ Uso: `/registrar [PAR]` (Registra la última señal sugerida para ese par)"
            
            pair = parts[1].upper()
            # This is a bit tricky since we don't store "last_signal" in CommandHandler, 
            # but we can re-analyze quickly or the user can do it manually.
            # Let's keep it simple for now: the user can register manually with more params if needed,
            # or we can implement a 'last_signals' cache in TradingAgent.
            # Actually, let's just implement a manual registration: /registrar PAR BUY ENTRY TP SL LOTS
            if len(parts) < 6:
                return "❌ Uso: `/registrar [PAR] [BUY/SELL] [ENTRY] [TP] [SL] [LOTS]`"
            
            try:
                pair = parts[1].upper()
                direction = parts[2].upper()
                entry = float(parts[3])
                tp = float(parts[4])
                sl = float(parts[5])
                lots = float(parts[6]) if len(parts) > 6 else 0.01
                
                self.agent.trade_tracker.register_trade(pair, direction, entry, tp, sl, lots)
                return f"✅ *Operación Registrada*: {direction} {pair} @ {entry}. Monitoreando Break Even..."
            except Exception as e:
                return f"❌ Error en formato: `{str(e)}`"
                
        else:
            # If it's not a command (doesn't start with /), treat as natural language
            if not comando.startswith("/"):
                return brain_handler.procesar_lenguaje_natural(comando)
                
            return f"❓ Comando no reconocido: `{cmd}`. Usa `/help` para ver la lista de las 3 cabezas."

    def _ejecutar_analisis_remoto(self, pair: str) -> str:
        """Execute granular dual analysis for both Scalper and Sniper."""
        try:
            logger.info(f"Análisis remoto solicitado para {pair} (Dual Mode)")
            
            profiles = config.trading.get("profiles", {})
            results = []
            
            for prof_name, prof_cfg in profiles.items():
                ctx_cfg = config.get_profile_config(prof_name)
                signal = self.agent.analyze_pair(pair, config_override=ctx_cfg)
                
                name = prof_cfg.get("name", prof_name)
                emoji = "⚡" if "Scalper" in name else "🎯"
                
                if signal:
                    direction = signal.direction.upper()
                    dir_emoji = "🚀" if direction == "BUY" else "🔻"
                    result = (
                        f"{emoji} *{name}*: {dir_emoji} *{direction}*\n"
                        f"   └ E: `{signal.entry_price:.5f}` | TP: `{signal.take_profit:.5f}` | SL: `{signal.stop_loss:.5f}`\n"
                        f"   └ Prob: `{signal.probability:.1%}` | MC: `{signal.monte_carlo_prob:.1%}`"
                    )
                else:
                    result = f"{emoji} *{name}*: ❌ Sin señal (Wait)"
                
                results.append(result)
            
            response = f"🐲 *ANÁLISIS DUAL: {pair}*\n"
            response += "------------------------------------------\n"
            response += "\n\n".join(results)
            response += "\n\n💡 _Basado en condiciones actuales de mercado._"
            
            return response
            
        except Exception as e:
            logger.error(f"Error en análisis remoto: {e}")
            return f"❌ Error analizando {pair}: {str(e)}"

    def _ejecutar_analisis_portafolio(self, pairs: list) -> str:
        """Analyze multiple pairs in one go."""
        summary = "📂 *REPORTE DE PORTAFOLIO*\n"
        summary += "Analizando pares de alto rendimiento...\n\n"
        
        for pair in pairs:
            # Short summary for portfolio
            signals = []
            profiles = config.trading.get("profiles", {})
            for prof_name in profiles:
                ctx_cfg = config.get_profile_config(prof_name)
                s = self.agent.analyze_pair(pair, config_override=ctx_cfg)
                if s:
                    signals.append(f"{prof_name[0].upper()}:{s.direction[0].upper()}")
            
            status = " | ".join(signals) if signals else "💤 No signals"
            summary += f"• *{pair}*: {status}\n"
            
        summary += "\nUse `/analiza [PAR]` para detalles granulares."
        return summary
