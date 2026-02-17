#!/usr/bin/env python3
"""
MCP Server for Trading Analysis Agent
Exposes trading agent functionality as MCP tools for VS Code integration
"""
import sys
import json
from pathlib import Path

# Add trading agent to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
except ImportError:
    print("ERROR: MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

from src.trading_agent import TradingAgent
from src.utils.logger import logger
from src.utils.config import config

app = Server("trading-analyzer")

# Global trading agent instance
agent = None

def get_agent():
    """Get or create trading agent instance."""
    global agent
    if agent is None:
        agent = TradingAgent()
    return agent

@app.list_tools()
async def list_tools():
    """List available trading analysis tools."""
    return [
        {
            "name": "analyze_pair",
            "description": "Analyze a currency pair and generate trading signal if conditions are met. Returns detailed signal with entry, stop loss, take profit, probability, and justifications.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "pair": {
                        "type": "string",
                        "description": "Currency pair to analyze (e.g., EURUSD, GBPUSD, USDJPY)"
                    }
                },
                "required": ["pair"]
            }
        },
        {
            "name": "analyze_multiple_pairs",
            "description": "Analyze multiple currency pairs and return all signals found",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "pairs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of currency pairs to analyze (e.g., ['EURUSD', 'GBPUSD'])"
                    }
                },
                "required": ["pairs"]
            }
        },
        {
            "name": "get_system_status",
            "description": "Get current status and configuration of the trading analysis system",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "get_configured_pairs",
            "description": "Get list of currency pairs configured for analysis",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        }
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    """Execute trading analysis tools."""
    
    if name == "analyze_pair":
        pair = arguments["pair"].upper()
        
        try:
            trading_agent = get_agent()
            signal = trading_agent.analyze_pair(pair)
            
            if signal:
                return {
                    "content": [{
                        "type": "text",
                        "text": signal.format_for_display()
                    }]
                }
            else:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"""
❌ No se generó señal para {pair}

Las condiciones de mercado no cumplen los criterios mínimos del sistema.

Posibles razones:
- Tendencia H4 no suficientemente clara
- Falta de alineación entre timeframes
- RSI en zona extrema
- Probabilidad por debajo del umbral (65%)
- Precio no cerca de niveles clave de soporte/resistencia

Recomendación: Esperar mejores condiciones de mercado o probar con otro par.
"""
                    }]
                }
        except Exception as e:
            logger.error(f"Error analyzing {pair}: {e}")
            return {
                "content": [{
                    "type": "text",
                    "text": f"❌ Error analizando {pair}: {str(e)}\n\nVerifica que las API keys estén configuradas correctamente en config/api_keys.json"
                }]
            }
    
    elif name == "analyze_multiple_pairs":
        pairs = [p.upper() for p in arguments["pairs"]]
        
        try:
            trading_agent = get_agent()
            results = trading_agent.analyze_multiple_pairs(pairs)
            
            signals_found = [(pair, signal) for pair, signal in results.items() if signal is not None]
            
            if signals_found:
                output = f"✅ Encontradas {len(signals_found)} señales de {len(pairs)} pares analizados:\n\n"
                output += "="*60 + "\n\n"
                
                for pair, signal in signals_found:
                    output += signal.format_for_display() + "\n"
                    output += "="*60 + "\n\n"
                
                # Summary
                output += f"\n📊 Resumen:\n"
                output += f"   - Pares analizados: {len(pairs)}\n"
                output += f"   - Señales generadas: {len(signals_found)}\n"
                output += f"   - Tasa de señales: {len(signals_found)/len(pairs)*100:.1f}%\n"
            else:
                output = f"""
❌ No se encontraron señales en ninguno de los {len(pairs)} pares analizados.

Pares analizados: {', '.join(pairs)}

Esto es normal cuando las condiciones de mercado no son favorables.
El sistema requiere que se cumplan 5 criterios estrictos para generar una señal.

Recomendación: 
- Esperar mejores condiciones de mercado
- Probar con otros pares
- Revisar los logs en logs/ para ver qué criterios no se cumplen
"""
            
            return {
                "content": [{
                    "type": "text",
                    "text": output
                }]
            }
        except Exception as e:
            logger.error(f"Error analyzing multiple pairs: {e}")
            return {
                "content": [{
                    "type": "text",
                    "text": f"❌ Error analizando pares: {str(e)}"
                }]
            }
    
    elif name == "get_system_status":
        try:
            trading_agent = get_agent()
            
            status = f"""
╔══════════════════════════════════════════════════════════════╗
║         📊 Estado del Sistema de Trading                    ║
╚══════════════════════════════════════════════════════════════╝

💰 Configuración de Capital:
   - Capital: ${trading_agent.capital:,.2f}
   - Riesgo por operación: {config.get_trading_config('risk_management.max_risk_per_trade_percent')}%
   - Riesgo máximo por trade: ${trading_agent.capital * config.get_trading_config('risk_management.max_risk_per_trade_percent') / 100:,.2f}

📈 Parámetros de Trading:
   - Umbral de probabilidad: {config.get_trading_config('probability.min_threshold'):.0%}
   - Risk/Reward mínimo: 1:{config.get_trading_config('risk_management.min_risk_reward_ratio')}
   - Multiplicador ATR para SL: {config.get_trading_config('risk_management.atr_multiplier_stop_loss')}

🔌 APIs Configuradas:
   - API principal: {config.primary_api_provider}
   - APIs de respaldo: {', '.join(config.fallback_api_providers)}

📋 Pares Configurados ({len(config.pairs)}):
   {', '.join(config.pairs)}

⏱️  Timeframes de Análisis:
   - Corto plazo: {config.timeframes.get('short', 'H1')}
   - Medio plazo: {config.timeframes.get('medium', 'H4')}
   - Largo plazo: {config.timeframes.get('long', 'D1')}

✅ Sistema operativo y listo para análisis
"""
            
            return {
                "content": [{
                    "type": "text",
                    "text": status
                }]
            }
        except Exception as e:
            return {
                "content": [{
                    "type": "text",
                    "text": f"❌ Error obteniendo estado: {str(e)}"
                }]
            }
    
    elif name == "get_configured_pairs":
        try:
            pairs = config.pairs
            
            output = f"""
📋 Pares de Divisas Configurados ({len(pairs)}):

"""
            for i, pair in enumerate(pairs, 1):
                output += f"   {i}. {pair}\n"
            
            output += f"""

Para analizar un par específico, usa:
   analyze_pair con pair="EURUSD"

Para analizar todos los pares, usa:
   analyze_multiple_pairs con pairs={json.dumps(pairs)}
"""
            
            return {
                "content": [{
                    "type": "text",
                    "text": output
                }]
            }
        except Exception as e:
            return {
                "content": [{
                    "type": "text",
                    "text": f"❌ Error obteniendo pares: {str(e)}"
                }]
            }

if __name__ == "__main__":
    import asyncio
    
    try:
        asyncio.run(stdio_server(app))
    except KeyboardInterrupt:
        logger.info("MCP Server stopped by user")
    except Exception as e:
        logger.error(f"MCP Server error: {e}")
        sys.exit(1)
