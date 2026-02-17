#!/usr/bin/env python3
"""
Trading Analysis Agent - Main Entry Point

Sistema de análisis de mercados forex que proporciona señales de trading
con probabilidad calculada y gestión de riesgo completa.
"""
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.trading_agent import TradingAgent
from src.utils.logger import logger
from src.utils.config import config
from src.tracking.capital_manager import CapitalManager
from src.tracking.trade_tracker import TradeTracker
from src.analysis.backtester import Backtester, BacktestResult
from src.utils.notificador import Notificador
from src.utils.command_handler import CommandHandler


def print_banner():
    """Print application banner."""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║         🎯 TRADING ANALYSIS AGENT v1.0                      ║
║         Sistema de Análisis Forex con IA                    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def print_risk_disclaimer():
    """Print risk disclaimer."""
    disclaimer = """
⚠️  ADVERTENCIA DE RIESGO
═══════════════════════════════════════════════════════════════

Este sistema proporciona análisis y señales de trading SOLO con fines
informativos. NO ejecuta operaciones automáticamente.

- El trading de divisas conlleva un alto nivel de riesgo
- Puede perder todo su capital invertido
- Las señales no garantizan resultados
- El usuario asume toda responsabilidad por sus operaciones
- Consulte con un asesor financiero profesional

═══════════════════════════════════════════════════════════════
"""
    print(disclaimer)


def analyze_single_pair(agent: TradingAgent, pair: str):
    """Analyze a single currency pair with all available profiles."""
    profiles = config.trading.get("profiles", {})
    signals_found = 0
    
    for prof_name in profiles:
        prof_cfg = config.get_profile_config(prof_name)
        signal = agent.analyze_pair(pair, config_override=prof_cfg)
        
        if signal:
            print(f"\n🎯 SEÑAL DETECTADA - PERFIL: {prof_cfg.get('name', prof_name)}")
            print(signal.format_for_display())
            signals_found += 1
            
    if signals_found == 0:
        logger.info(f"\n❌ No se generó señal para {pair} en ningún perfil.")
        logger.info("Recomendación: Esperar mejores condiciones de mercado.\n")


def analyze_all_pairs(agent: TradingAgent):
    """Analyze all configured pairs."""
    results = agent.analyze_multiple_pairs()
    
    # Print all signals
    signals = [s for s in results.values() if s is not None]
    
    if signals:
        print("\n" + "="*60)
        print(f"📊 SEÑALES ENCONTRADAS ({len(signals)})")
        print("="*60 + "\n")
        
        for signal in signals:
            print(signal.format_for_display())
            print("\n" + "-"*60 + "\n")
    else:
        logger.info("\n❌ No se encontraron señales en ningún par")
        logger.info("Recomendación: Esperar mejores condiciones de mercado.\n")


def scanner_mode(agent: TradingAgent):
    """Run in continuous scanning mode with API optimization."""
    import time
    from datetime import datetime
    from src.api.api_manager import api_manager
    notificador = Notificador()
    selected_pairs = ["AUDUSD", "GBPUSD", "USDCAD"]
    
    print("\n🚀 CONFIGURACIÓN DE MODO ESCÁNER INTELIGENTE")
    print("============================================================")
    print(f"Pares del Golden Trio: {', '.join(selected_pairs)}")
    
    budget_cfg = config.get_trading_config("budget_management")
    peak_hours = budget_cfg.get("peak_hours", [])
    dead_hours = budget_cfg.get("dead_hours", [])
    intervals = budget_cfg.get("intervals", {})
    
    # Initialize Tracking
    trade_tracker = TradeTracker()
    cmd_handler = CommandHandler(agent)

    logger.info(f"\n🚀 ESCÁNER ACTIVO: {len(selected_pairs)} pares")
    logger.info("Programador Inteligente activado (Heatmap Mode)")
    logger.info("Presiona Ctrl+C para detener.\n")
    
    iteration = 1
    trend_cache = {} # Cache for D1/H4 data
    
    while True:
        try:
            start_req = api_manager.request_count
            logger.info(f"--- Ciclo #{iteration} | {datetime.now().strftime('%H:%M:%S')} ---")
            
            # Tiered Refresh: Rejfresh D1/H4 only every 4 hours (or 4 cycles if interval=60m)
            refresh_trends = (iteration == 1) or (iteration % 4 == 0)
            
            signals_found = []
            profiles = config.trading.get("profiles", {})
            
            for pair in selected_pairs:
                logger.info(f"Escaneando {pair} (Dual Mode)...")
                
                # Fetch H1 always, re-use H4/D1 if possible (Economy Mode)
                h1_interval = "15min" # Unified fetch for scalping compatibility
                h4_interval = config.timeframes.get('medium', 'H4')
                d1_interval = config.timeframes.get('long', 'D1')
                
                # Manual data bundle
                manual_data = {}
                manual_data[h1_interval] = api_manager.get_forex_data(pair, h1_interval, outputsize="full")
                
                if refresh_trends or pair not in trend_cache:
                    logger.info(f"Refrescando tendencias (D1/H4) para {pair}")
                    manual_data[h4_interval] = api_manager.get_forex_data(pair, h4_interval, outputsize="full")
                    manual_data[d1_interval] = api_manager.get_forex_data(pair, d1_interval, outputsize="full")
                    trend_cache[pair] = {
                        h4_interval: manual_data[h4_interval],
                        d1_interval: manual_data[d1_interval]
                    }
                else:
                    manual_data.update(trend_cache[pair])
                
                # Check for closures or management advice
                current_price = manual_data[h1_interval].iloc[-1]['close']
                closed = trade_tracker.check_trades(pair, current_price)
                if closed:
                    for trade in closed:
                        res_msg = "✅ *TP ALCANZADO*" if trade['status'] == 'TP_HIT' else "❌ *SL ALCANZADO*"
                        notificador.enviar_mensaje(f"{res_msg}\nPar: {pair}\nP&L: ${trade['profit_loss']:+.2f}")
                
                # Management advice (BE)
                advices = trade_tracker.check_management(pair, current_price)
                for advice in advices:
                    notificador.enviar_mensaje(advice)

                # Evaluate profiles
                active_profiles = list(profiles.keys())
                
                # Dynamic Logic for Tokyo Daybreak (Asia Scalper)
                # Activate 30m before 00:00 UTC (i.e., 23:30 UTC) until 09:00 UTC
                now_utc = datetime.utcnow()
                is_asia_window = (now_utc.hour == 23 and now_utc.minute >= 30) or (0 <= now_utc.hour < 9)
                
                if "asia_scalper" not in active_profiles and is_asia_window:
                    active_profiles.append("asia_scalper")
                elif "asia_scalper" in active_profiles and not is_asia_window:
                    # If it was manually enabled but outside window, we keep it, 
                    # but if it was auto-added, we could remove it. 
                    # For now, let's just make it always available if is_asia_window.
                    pass

                for prof_name in active_profiles:
                    prof_cfg = config.get_profile_config(prof_name)
                    signal = agent.analyze_pair(pair, manual_data=manual_data, config_override=prof_cfg)
                    if signal:
                        # Tag strategy in notification
                        signal.strategy_name = prof_cfg.get('name', prof_name)
                        
                        # Add Limit Order recommendation for Asia
                        if prof_name == "asia_scalper":
                            signal.entry_reason = f"🕒 [PRE-SESSION ASIA] {signal.entry_reason}\n💡 RECOMENDACIÓN: Colocar ORDEN LIMIT para capturar el movimiento inicial."
                        
                        signals_found.append(signal)
            
            cost = api_manager.request_count - start_req
            logger.info(f"Consumo del ciclo: {cost} solicitudes (Total sesión: {api_manager.request_count})")
            
            if signals_found:
                print("\n" + "🚨" * 30)
                print(f"     ¡SEÑALES ENCONTRADAS! ({len(signals_found)})")
                print("🚨" * 30 + "\n")
                for s in signals_found:
                    print(f"\n🚨 [{s.strategy_name}] SEÑAL DETECTADA 🚨")
                    print(s.format_for_display())
                    notificador.enviar_alerta_sniper(s.to_dict())
                print("\a") # Sound alert
            
            iteration += 1
            
            # Smart Interval Calculation
            current_hour = datetime.now().hour
            if current_hour in peak_hours:
                mode = "SNIPER (Peak)"
                wait_m = intervals.get("peak", 15)
            elif current_hour in dead_hours:
                mode = "ECO (Dead)"
                wait_m = intervals.get("dead", 120)
            else:
                mode = "VIGILANCIA (Normal)"
                wait_m = intervals.get("normal", 60)
                
            logger.info(f"Modo: {mode} | Próximo escaneo en {wait_m} min")
            
            # Bidirectional Polling Loop (Alpha Link)
            wait_seconds = int(wait_m * 60)
            polling_interval = 15 # Check for commands every 15 seconds
            end_wait = time.time() + wait_seconds
            
            while time.time() < end_wait:
                try:
                    commands = notificador.obtener_comandos()
                    for cmd_data in commands:
                        text = cmd_data.get("text", "")
                        
                        # Special case for /stop
                        if text.lower() == "/stop":
                            notificador.enviar_mensaje("🛑 *Comando de Parada Recibido.*\nDeteniendo el escáner remoto. ¡Hasta pronto!")
                            logger.info("🛑 Escáner detenido vía comando remoto.")
                            return
                            
                        # Notify user analysis is processing if it's /analiza
                        if text.lower().startswith("/analiza"):
                            pair_req = text.split()[-1].upper() if len(text.split()) > 1 else "?"
                            notificador.enviar_mensaje(f"🔍 *Analizando {pair_req}...* (Esto puede tardar unos segundos)")
                            
                        # Process other commands
                        response = cmd_handler.procesar_comando(text)
                        if response:
                            notificador.enviar_mensaje(response)
                            
                except Exception as poll_e:
                    logger.debug(f"Error en polling de comandos: {poll_e}")
                
                # Sleep in small increments to remain responsive
                time.sleep(min(polling_interval, max(0, end_wait - time.time())))
            
        except KeyboardInterrupt:
            logger.info("\n👋 Escáner detenido.")
            break
        except Exception as e:
            logger.error(f"Error en escáner: {e}")
            time.sleep(60)


def _prop_firm_mode(agent: TradingAgent, capital_mgr: CapitalManager):
    """Specialized mode for Prop Firm traders."""
    print("\n" + "="*60)
    print("🏆 BIENVENIDO AL MODO PROP FIRM (FTMO / MYFOREXFUNDS / ETC)")
    print("="*60)
    
    # 1. Configurar Capital y Riesgo si no están listos
    current_cap = capital_mgr.get_capital()
    print(f"\n💰 Capital actual configurado: ${current_cap:,.2f}")
    change_cap = input("¿Deseas ajustar el CAPITAL de la cuenta? (s/n): ").lower()
    if change_cap == 's':
        try:
            new_cap = float(input("   Monto de la cuenta (ej: 100000): "))
            capital_mgr.update_capital(new_cap)
            agent.update_capital(new_cap)
        except ValueError:
            print("⚠️ Monto inválido. Manteniendo actual.")

    # 2. Seleccionar Modo Prop
    print("\n📋 SELECCIONA TU OBJETIVO:")
    print("  1. CHALLENGE (Modo Agresivo - Pasar Prueba)")
    print("     - Riesgo: 1.0% | RR: 1.5+ | Filtros balanceados")
    print("  2. FUNDED (Modo Conservador - Retiros/Profit)")
    print("     - Riesgo: 0.5% | RR: 2.0+ | Filtros ultra-estrictos")
    print("  3. DOPAMINA (Modo Scalping Diario - Alta Probabilidad)")
    print("     - Riesgo: 0.5% | RR: 1.1 a 1.5 | Búsqueda de 'Sweet Spot'")
    print("  0. Volver")
    
    goal = input("\n🎯 Opción > ")
    
    if goal == "1":
        profile = "prop_challenge"
        mode_func = agent.analyze_pair
    elif goal == "2":
        profile = "prop_funded"
        mode_func = agent.analyze_pair
    elif goal == "3":
        profile = "prop_scalper"
        mode_func = agent.analyze_scalp_pair
    else:
        return

    prof_cfg = config.get_profile_config(profile)
    risk_pct = prof_cfg.get("risk_management", {}).get("risk_per_trade", 0.5)
    
    # Update agent with profile-specific risk
    agent.update_risk_percent(risk_pct)
    capital_mgr.update_risk_percentage(risk_pct)
    
    print(f"\n✅ MODO ACTIVADO: {prof_cfg['name']}")
    print(f"📊 Riesgo por operación: {risk_pct}% (${capital_mgr.get_risk_amount():,.2f})")
    
    # 3. Analizar Golden Trio
    pairs = ["EURUSD", "GBPUSD", "USDJPY"]
    print(f"\n🔍 Analizando 'Golden Trio' ({', '.join(pairs)})...")
    
    found = 0
    for pair in pairs:
        # If it's the standard mode_func (analyze_pair), we pass the config override
        # If it's analyze_scalp_pair, it handles its own internal configs
        if goal == "3":
            signal = mode_func(pair)
        else:
            signal = mode_func(pair, config_override=prof_cfg)
            
        if signal:
            print(f"\n🚀 SEÑAL {prof_cfg['name']} DETECTADA!")
            print(signal.format_for_display())
            found += 1
    
    if found == 0:
        print("\n😴 No hay señales de alta probabilidad en este momento.")
        print("Recomendación: Vuelve en la siguiente ventana operativa (Asia o London).")
    
    input("\nPresiona ENTER para volver al menú principal...")


def interactive_mode(agent: TradingAgent):
    """Run in interactive mode."""
    # Initialize tracking modules
    capital_mgr = CapitalManager()
    trade_tracker = TradeTracker()
    
    # Store last signal for registration
    last_signal = {}
    
    # Synchronize agent with saved settings
    agent.update_capital(capital_mgr.get_capital())
    agent.update_risk_percent(capital_mgr.get_risk_percentage())
    
    def _menu_cambiar_perfil(current_agent: TradingAgent):
        """Menu for switching strategy profiles."""
        import json
        from pathlib import Path
        from src.core.trading_agent import TradingAgent # Assuming TradingAgent is in src.core
        
        print("\n🔄 SELECCIÓN DE PERFIL DE ESTRATEGIA")
        print("============================================================")
        
        profiles = config.trading.get("profiles", {})
        active = config.trading.get("active_profile")
        
        prof_list = list(profiles.keys())
        for i, (key, data) in enumerate(profiles.items(), 1):
            mark = "✅" if key == active else "  "
            desc = data.get("name", key)
            print(f"  {i}️  {mark} {desc} ({key})")
            
        print("  0️  Volver")
        print("============================================================")
        
        choice = input("\n🎯 Selecciona perfil > ").strip()
        
        if choice == "0":
            return current_agent # Return current agent if no change
            
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(prof_list):
                new_profile = prof_list[idx]
                
                # Update config file
                # Assuming config.py is in the parent directory of the script running interactive_mode
                # and config/trading_config.json is relative to the project root.
                # This path might need adjustment based on actual project structure.
                config_path = Path(__file__).parent.parent / "config" / "trading_config.json"
                with open(config_path, 'r') as f:
                    data = json.load(f)
                
                data["active_profile"] = new_profile
                with open(config_path, 'w') as f:
                    json.dump(data, f, indent=4)
                
                # Reload config
                config.reload()
                
                # Re-initialize agent with new config
                # This will create a new agent instance, so we need to return it
                new_agent = TradingAgent(current_agent.capital)
                
                print(f"\n✅ Perfil CAMBIADO a: {new_profile}")
                print("⚠️ El sistema ha sido reiniciado con los nuevos parámetros.")
                return new_agent
            else:
                print("\n❌ Selección inválida.")
                return current_agent
        except ValueError:
            print("\n❌ Debes ingresar un número.")
            return current_agent
        except Exception as e:
            logger.error(f"Error al cambiar perfil: {e}")
            return current_agent
            
    def show_menu():
        """Display numbered menu."""
        print("\n🤖 Modo Interactivo - Menú Principal")
        print("=" * 60)
        print("  1️⃣  Analizar par específico")
        print("  2️⃣  Analizar todos los pares")
        print("  3️⃣  MODO ESCÁNER (Loop Continuo)")
        print("  4️⃣  Ver pares configurados")
        print("  5️⃣  Ver estado del sistema")
        print("  6️⃣  Configurar capital")
        print("  7️⃣  Configurar riesgo (%)")
        print("  8️⃣  Registrar operación")
        print("  9️⃣  Ver operaciones abiertas")
        print("  🔟  Ver historial de operaciones")
        print("  📊  Estadísticas (11)")
        print("  📜  Backtesting (12)")
        print("  🔄  Cambiar Perfil (13)")
        print("  📋  Ayuda (14)")
        print("  🏆  MODO PROP FIRM (15)")
        print("  🧠  ASISTENTE MANUAL (16)")
        print("  0️⃣  Salir")
        print("=" * 60)
        print("\n💡 Tip: Puedes usar números (1-15) o comandos de texto")
        print("    Ejemplo: '1' o 'analiza EURUSD'\n")
    
    show_menu()
    
    while True:
        try:
            command = input("🎯 > ").strip()
            
            if not command:
                continue
            
            # Handle numeric menu options
            if command.isdigit():
                option = int(command)
                
                if option == 0:
                    logger.info("👋 Cerrando Trading Agent...")
                    break
                
                elif option == 1:
                    pair = input("  📊 Ingresa el par (ej: EURUSD): ").strip().upper()
                    if pair:
                        # Check open trades
                        current_price = None
                        signal = agent.analyze_pair(pair)
                        
                        if signal:
                            last_signal[pair] = {
                                'direction': signal.direction,
                                'entry': signal.entry_price,
                                'tp': signal.take_profit,
                                'sl': signal.stop_loss,
                                'lot': signal.lot_size
                            }
                            current_price = signal.entry_price
                            print(signal.format_for_display())
                        else:
                            logger.info(f"\n❌ No se generó señal para {pair}")
                            logger.info("Recomendación: Esperar mejores condiciones de mercado.\n")
                        
                        if current_price:
                            closed = trade_tracker.check_trades(pair, current_price)
                            if closed:
                                for trade in closed:
                                    result = "✅ TP ALCANZADO" if trade['status'] == 'TP_HIT' else "❌ SL ALCANZADO"
                                    print(f"\n{result}: {trade['id']}")
                                    print(f"P&L: ${trade['profit_loss']:+.2f} ({trade['pips']:+.1f} pips)\n")
                    else:
                        print("❌ Debes especificar un par")
                
                elif option == 2:
                    analyze_all_pairs(agent)
                
                elif option == 3:
                    scanner_mode(agent)
                
                elif option == 4:
                    pairs = config.pairs
                    print(f"\n📋 Pares configurados ({len(pairs)}):")
                    for i, pair in enumerate(pairs, 1):
                        print(f"   {i}. {pair}")
                    print()
                
                elif option == 5:
                    print("\n📊 Estado del Sistema:")
                    print(f"   - Capital: ${agent.capital:,.2f}")
                    print(f"   - Riesgo por operación: {capital_mgr.get_risk_percentage()}%")
                    print(f"   - Umbral de probabilidad: {config.get_trading_config('probability.min_threshold'):.0%}")
                    print(f"   - API principal: {config.primary_api_provider}")
                    print()
                
                elif option == 6:
                    new_capital = input("  💰 Ingresa el nuevo capital: $").strip()
                    try:
                        new_capital = float(new_capital)
                        capital_mgr.update_capital(new_capital)
                        agent.update_capital(new_capital)
                        risk_amount = capital_mgr.get_risk_amount()
                        print(f"\n✅ Capital actualizado: ${new_capital:,.2f}")
                        print(f"📊 Riesgo por operación ({capital_mgr.get_risk_percentage()}%): ${risk_amount:,.2f}\n")
                    except ValueError:
                        print("❌ El monto debe ser un número válido")
                
                elif option == 7:
                    new_risk = input("  🎲 Ingresa el nuevo porcentaje de riesgo (ej: 1.5): ").strip()
                    try:
                        new_risk = float(new_risk)
                        capital_mgr.update_risk_percentage(new_risk)
                        agent.update_risk_percent(new_risk)
                        risk_amount = capital_mgr.get_risk_amount()
                        print(f"\n✅ Riesgo actualizado: {new_risk}%")
                        print(f"📊 Capital actual: ${agent.capital:,.2f}")
                        print(f"💰 Monto en riesgo: ${risk_amount:,.2f}\n")
                    except ValueError:
                        print("❌ El porcentaje debe ser un número válido")

                elif option == 8:
                    pair = input("  📊 Ingresa el par a registrar (ej: EURUSD): ").strip().upper()
                    if pair in last_signal:
                        sig = last_signal[pair]
                        trade_tracker.register_trade(
                            pair=pair,
                            direction=sig['direction'],
                            entry_price=sig['entry'],
                            take_profit=sig['tp'],
                            stop_loss=sig['sl'],
                            lot_size=sig['lot']
                        )
                        print(f"\n✅ Operación registrada. Monitoreando automáticamente...\n")
                    else:
                        print(f"❌ No hay señal reciente para {pair}")
                        print(f"Primero ejecuta: analiza {pair}\n")
                
                elif option == 9:
                    open_trades = trade_tracker.get_open_trades()
                    if open_trades:
                        print(f"\n📊 OPERACIONES ABIERTAS ({len(open_trades)}):")
                        print()
                        for i, trade in enumerate(open_trades, 1):
                            print(f"{i}. {trade['pair']} - {trade['direction']}")
                            print(f"   Entrada: {trade['entry_price']:.5f}")
                            print(f"   TP: {trade['take_profit']:.5f} | SL: {trade['stop_loss']:.5f}")
                            print(f"   Lote: {trade['lot_size']} | ID: {trade['id']}")
                            print()
                    else:
                        print("\n📊 No hay operaciones abiertas\n")
                
                elif option == 10:
                    closed_trades = trade_tracker.get_closed_trades(limit=10)
                    if closed_trades:
                        print(f"\n📜 HISTORIAL DE OPERACIONES (últimas {len(closed_trades)}):")
                        print()
                        for trade in reversed(closed_trades):
                            result = "✅" if trade['profit_loss'] > 0 else "❌"
                            print(f"{result} {trade['pair']} {trade['direction']} - {trade['entry_time'][:10]}")
                            print(f"   Entrada: {trade['entry_price']:.5f} | Salida: {trade['exit_price']:.5f} ({trade['status']})")
                            print(f"   P&L: ${trade['profit_loss']:+.2f} ({trade['pips']:+.1f} pips)")
                            print()
                    else:
                        print("\n📜 No hay operaciones en el historial\n")
                
                elif option == 11: # Statistics
                    stats = trade_tracker.get_statistics()
                    capital = capital_mgr.get_capital()
                    
                    if stats['total_trades'] > 0:
                        win_rate = (stats['winning_trades'] / stats['total_trades']) * 100
                        total_pl = stats['total_profit'] - stats['total_loss']
                        avg_win = stats['total_profit'] / stats['winning_trades'] if stats['winning_trades'] > 0 else 0
                        avg_loss = stats['total_loss'] / stats['losing_trades'] if stats['losing_trades'] > 0 else 0
                        
                        print("\n📊 ESTADÍSTICAS DE RENDIMIENTO")
                        print("="*50)
                        print(f"\nCapital Actual: ${capital:,.2f}")
                        print(f"P&L Total: ${total_pl:+,.2f}")
                        print(f"\nOperaciones:")
                        print(f"  Total: {stats['total_trades']}")
                        print(f"  Ganadoras: {stats['winning_trades']} ({win_rate:.1f}%)")
                        print(f"  Perdedoras: {stats['losing_trades']} ({100-win_rate:.1f}%)")
                        print(f"\nPromedio:")
                        print(f"  Ganancia: +${avg_win:.2f}")
                        print(f"  Pérdida: -${avg_loss:.2f}")
                        if avg_loss > 0:
                            rr_ratio = avg_win / avg_loss
                            print(f"  Risk/Reward: 1:{rr_ratio:.2f}")
                        print(f"\nRacha Actual: {abs(stats['current_streak'])} {'ganadoras 🔥' if stats['current_streak'] > 0 else 'perdedoras'}")
                        print(f"\nMejor Operación: +${stats['best_trade']:.2f}")
                        print(f"Peor Operación: ${stats['worst_trade']:.2f}")
                        print()
                    else:
                        print("\n📊 No hay estadísticas disponibles aún\n")
                
                elif option == 12: # Backtesting
                    pair = input("  📊 Ingresa el par para backtesting (ej: EURUSD): ").strip().upper()
                    days = input("  📅 Ingresa el número de días (ej: 30): ").strip()
                    try:
                        days = int(days)
                        backtester = Backtester(agent)
                        result = backtester.run(pair, days)
                        
                        print("\n📜 RESULTADOS DE BACKTESTING")
                        print("="*50)
                        print(f"Par: {result.pair} | Periodo: {days} días")
                        print(f"Operaciones totales: {result.total_trades}")
                        print(f"Win Rate: {result.win_rate:.1%}")
                        print(f"Profit Factor: {result.profit_factor:.2f}")
                        print(f"P&L Neto: ${result.net_profit:+.2f}")
                        print(f"Max Drawdown: ${result.max_drawdown:.2f}")
                        print("="*50)
                        
                        if result.trades:
                            ver_detalles = input("\n¿Deseas ver el detalle de las operaciones? (s/n): ").lower()
                            if ver_detalles == 's':
                                for t in result.trades:
                                    res = "✅" if t['profit_loss'] > 0 else "❌"
                                    print(f"{res} {t['timestamp']} | {t['direction']} | {t['status']} | {t['profit_loss']:+.2f}")
                        print()
                        
                    except ValueError:
                        print("❌ El número de días debe ser un entero válido")
                    except Exception as e:
                        logger.error(f"Error en backtesting: {e}")

                elif option == 13: # Change Profile
                    new_agent = _menu_cambiar_perfil(agent)
                    if new_agent is not agent: # If agent was re-initialized
                        agent = new_agent # Update the agent reference
                        # Re-synchronize capital and risk for the new agent instance
                        agent.update_capital(capital_mgr.get_capital())
                        agent.update_risk_percent(capital_mgr.get_risk_percentage())
                
                elif option == 14: # Help
                    show_menu()
                
                elif option == 15: # Prop Firm Mode
                    _prop_firm_mode(agent, capital_mgr)
                
                elif option == 16: # Manual Assistant
                    print("\n🧠 INICIANDO ASISTENTE DE TRADING MANUAL (DSS)")
                    print("="*60)
                    print("Analizando mercado con enfoque narrativo...")
                    
                    pairs = config.pairs
                    for pair in pairs:
                        print(f"\n🔍 Procesando {pair}...")
                        signal = agent.analyze_pair(pair)
                        if signal:
                            print(signal.format_for_display())
                        else:
                            print(f"⚪ {pair}: Sin señales claras, manteniendo neutralidad.")
                    
                    print("\n✅ Análisis manual completado.")
                    input("\nPresiona ENTER para volver al menú...")
                
                else:
                    print(f"❌ Opción inválida: {option}")
                    print("Usa números del 0 al 14, o escribe 'ayuda'\n")
                
                continue
            
            # Handle text commands
            command_lower = command.lower()
            
            if command_lower in ["salir", "exit", "quit", "q"]:
                logger.info("👋 Cerrando Trading Agent...")
                break
            
            elif command_lower in ["ayuda", "help", "menu", "?"]:
                show_menu()
            
            elif command_lower == "pares":
                pairs = config.pairs
                print(f"\n📋 Pares configurados ({len(pairs)}):")
                for i, pair in enumerate(pairs, 1):
                    print(f"   {i}. {pair}")
                print()
            
            elif command_lower == "estado":
                print("\n📊 Estado del Sistema:")
                print(f"   - Capital: ${agent.capital:,.2f}")
                print(f"   - Riesgo por operación: {capital_mgr.get_risk_percentage()}%")
                print(f"   - Umbral de probabilidad: {config.get_trading_config('probability.min_threshold'):.0%}")
                print(f"   - API principal: {config.primary_api_provider}")
                print()
            
            elif command_lower.startswith("configurar capital"):
                parts = command.split()
                if len(parts) >= 3:
                    try:
                        new_capital = float(parts[2])
                        capital_mgr.update_capital(new_capital)
                        agent.update_capital(new_capital)
                        risk_amount = capital_mgr.get_risk_amount()
                        print(f"\n✅ Capital actualizado: ${new_capital:,.2f}")
                        print(f"📊 Riesgo por operación ({capital_mgr.get_risk_percentage()}%): ${risk_amount:,.2f}\n")
                    except ValueError:
                        print("❌ El monto debe ser un número válido")
                else:
                    print("❌ Formato incorrecto. Uso: configurar capital [MONTO]")
                    print("   Ejemplo: configurar capital 5000\n")
            
            elif command_lower.startswith("configurar riesgo"):
                parts = command.split()
                if len(parts) >= 3:
                    try:
                        new_risk = float(parts[2])
                        capital_mgr.update_risk_percentage(new_risk)
                        agent.update_risk_percent(new_risk)
                        risk_amount = capital_mgr.get_risk_amount()
                        print(f"\n✅ Riesgo actualizado: {new_risk}%")
                        print(f"📊 Capital actual: ${agent.capital:,.2f}")
                        print(f"💰 Monto en riesgo: ${risk_amount:,.2f}\n")
                    except ValueError:
                        print("❌ El porcentaje debe ser un número válido")
                else:
                    print("❌ Formato incorrecto. Uso: configurar riesgo [PORCENTAJE]")
                    print("   Ejemplo: configurar riesgo 1.5\n")
            
            elif command_lower.startswith("backtest"):
                parts = command.split()
                if len(parts) >= 2:
                    pair = parts[1].upper()
                    days = 30
                    if len(parts) >= 3:
                        try:
                            days = int(parts[2])
                        except ValueError:
                            pass
                    
                    try:
                        backtester = Backtester(agent)
                        result = backtester.run(pair, days)
                        
                        print("\n📜 RESULTADOS DE BACKTESTING")
                        print("="*50)
                        print(f"Par: {result.pair} | Periodo: {days} días")
                        print(f"Win Rate: {result.win_rate:.1%} | Profit Factor: {result.profit_factor:.2f}")
                        print(f"P&L Neto: ${result.net_profit:+.2f}")
                        print("="*50 + "\n")
                    except Exception as e:
                        logger.error(f"Error en backtesting: {e}")
                else:
                    print("❌ Formato incorrecto. Uso: backtest [PAR] [DIAS]")
                    print("   Ejemplo: backtest EURUSD 30\n")
                parts = command.split()
                if len(parts) >= 3:
                    pair = parts[2].upper()
                    if pair in last_signal:
                        sig = last_signal[pair]
                        trade_tracker.register_trade(
                            pair=pair,
                            direction=sig['direction'],
                            entry_price=sig['entry'],
                            take_profit=sig['tp'],
                            stop_loss=sig['sl'],
                            lot_size=sig['lot']
                        )
                        print(f"\n✅ Operación registrada. Monitoreando automáticamente...\n")
                    else:
                        print(f"❌ No hay señal reciente para {pair}")
                        print(f"Primero ejecuta: analiza {pair}\n")
                else:
                    print("❌ Formato incorrecto. Uso: registrar operacion [PAR]")
                    print("   Ejemplo: registrar operacion EURUSD\n")
            
            elif command_lower == "ver abiertas":
                open_trades = trade_tracker.get_open_trades()
                if open_trades:
                    print(f"\n📊 OPERACIONES ABIERTAS ({len(open_trades)}):")
                    print()
                    for i, trade in enumerate(open_trades, 1):
                        print(f"{i}. {trade['pair']} - {trade['direction']}")
                        print(f"   Entrada: {trade['entry_price']:.5f}")
                        print(f"   TP: {trade['take_profit']:.5f} | SL: {trade['stop_loss']:.5f}")
                        print(f"   Lote: {trade['lot_size']} | ID: {trade['id']}")
                        print()
                else:
                    print("\n📊 No hay operaciones abiertas\n")
            
            elif command_lower == "ver historial":
                closed_trades = trade_tracker.get_closed_trades(limit=10)
                if closed_trades:
                    print(f"\n📜 HISTORIAL DE OPERACIONES (últimas {len(closed_trades)}):")
                    print()
                    for trade in reversed(closed_trades):
                        result = "✅" if trade['profit_loss'] > 0 else "❌"
                        print(f"{result} {trade['pair']} {trade['direction']} - {trade['entry_time'][:10]}")
                        print(f"   Entrada: {trade['entry_price']:.5f} | Salida: {trade['exit_price']:.5f} ({trade['status']})")
                        print(f"   P&L: ${trade['profit_loss']:+.2f} ({trade['pips']:+.1f} pips)")
                        print()
                else:
                    print("\n📜 No hay operaciones en el historial\n")
            
            elif command_lower == "ver estadisticas":
                stats = trade_tracker.get_statistics()
                capital = capital_mgr.get_capital()
                
                if stats['total_trades'] > 0:
                    win_rate = (stats['winning_trades'] / stats['total_trades']) * 100
                    total_pl = stats['total_profit'] - stats['total_loss']
                    avg_win = stats['total_profit'] / stats['winning_trades'] if stats['winning_trades'] > 0 else 0
                    avg_loss = stats['total_loss'] / stats['losing_trades'] if stats['losing_trades'] > 0 else 0
                    
                    print("\n📊 ESTADÍSTICAS DE RENDIMIENTO")
                    print("="*50)
                    print(f"\nCapital Actual: ${capital:,.2f}")
                    print(f"P&L Total: ${total_pl:+,.2f}")
                    print(f"\nOperaciones:")
                    print(f"  Total: {stats['total_trades']}")
                    print(f"  Ganadoras: {stats['winning_trades']} ({win_rate:.1f}%)")
                    print(f"  Perdedoras: {stats['losing_trades']} ({100-win_rate:.1f}%)")
                    print(f"\nPromedio:")
                    print(f"  Ganancia: +${avg_win:.2f}")
                    print(f"  Pérdida: -${avg_loss:.2f}")
                    if avg_loss > 0:
                        rr_ratio = avg_win / avg_loss
                        print(f"  Risk/Reward: 1:{rr_ratio:.2f}")
                    print(f"\nRacha Actual: {abs(stats['current_streak'])} {'ganadoras 🔥' if stats['current_streak'] > 0 else 'perdedoras'}")
                    print(f"\nMejor Operación: +${stats['best_trade']:.2f}")
                    print(f"Peor Operación: ${stats['worst_trade']:.2f}")
                    print()
                else:
                    print("\n📊 No hay estadísticas disponibles aún\n")
            
            elif command_lower.startswith("analiza"):
                parts = command.split()
                if len(parts) == 1:
                    # User just typed "analiza" without a pair
                    print("❌ Debes especificar un par o 'todos'")
                    print("   Ejemplos:")
                    print("   - analiza EURUSD")
                    print("   - analiza todos")
                    print("   O usa el menú: opción 1 o 2\n")
                elif len(parts) == 2:
                    if parts[1] == "todos":
                        analyze_all_pairs(agent)
                    else:
                        pair = parts[1].upper()
                        # Check open trades
                        current_price = None
                        signal = agent.analyze_pair(pair)
                        
                        if signal:
                            last_signal[pair] = {
                                'direction': signal.direction,
                                'entry': signal.entry_price,
                                'tp': signal.take_profit,
                                'sl': signal.stop_loss,
                                'lot': signal.lot_size
                            }
                            current_price = signal.entry_price
                            print(signal.format_for_display())
                        else:
                            logger.info(f"\n❌ No se generó señal para {pair}")
                            logger.info("Recomendación: Esperar mejores condiciones de mercado.\n")
                        
                        if current_price:
                            closed = trade_tracker.check_trades(pair, current_price)
                            if closed:
                                for trade in closed:
                                    result = "✅ TP ALCANZADO" if trade['status'] == 'TP_HIT' else "❌ SL ALCANZADO"
                                    print(f"\n{result}: {trade['id']}")
                                    print(f"P&L: ${trade['profit_loss']:+.2f} ({trade['pips']:+.1f} pips)\n")
                else:
                    print("❌ Formato incorrecto. Uso: analiza [PAR] o analiza todos\n")
            
            else:
                print(f"❌ Comando no reconocido: '{command}'")
                print("💡 Usa números (1-10) o escribe 'ayuda' para ver opciones\n")
        
        except KeyboardInterrupt:
            print("\n\n👋 Cerrando Trading Agent...")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Trading Analysis Agent - Sistema de análisis forex con IA"
    )
    
    parser.add_argument(
        "command",
        nargs="?",
        help="Comando a ejecutar: analiza [PAR], analiza todos, o modo interactivo"
    )
    
    parser.add_argument(
        "pair",
        nargs="?",
        help="Par de divisas a analizar (ej: EURUSD)"
    )
    
    parser.add_argument(
        "--capital",
        type=float,
        help="Capital de trading (por defecto: valor en configuración)"
    )
    
    parser.add_argument(
        "--no-disclaimer",
        action="store_true",
        help="Omitir advertencia de riesgo"
    )
    
    args = parser.parse_args()
    
    # Print banner
    print_banner()
    
    # Print disclaimer unless disabled
    if not args.no_disclaimer:
        print_risk_disclaimer()
        input("Presiona ENTER para continuar...")
        print()
    
    try:
        # Initialize agent
        logger.info("Inicializando Trading Agent...")
        agent = TradingAgent(capital=args.capital)
        
        # Determine mode
        if args.command is None:
            # Interactive mode
            interactive_mode(agent)
        
        elif args.command.lower() == "scanner":
            scanner_mode(agent)
        
        elif args.command.lower() == "analiza":
            if args.pair and args.pair.lower() == "todos":
                analyze_all_pairs(agent)
            elif args.pair:
                analyze_single_pair(agent, args.pair.upper())
            else:
                print("❌ Especifica un par o 'todos'")
                print("Uso: python main.py analiza [PAR]")
                print("     python main.py analiza todos")
        
        else:
            print(f"❌ Comando no reconocido: '{args.command}'")
            print("\nUso:")
            print("  python main.py                    # Modo interactivo")
            print("  python main.py scanner            # Modo escáner continuo")
            print("  python main.py analiza EURUSD     # Analizar par específico")
            print("  python main.py analiza todos      # Analizar todos los pares")
    
    except KeyboardInterrupt:
        print("\n\n👋 Programa interrumpido por el usuario")
        sys.exit(0)
    
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
