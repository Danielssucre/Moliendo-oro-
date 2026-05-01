
import sys
import os
import time
import logging

# Set up paths
current_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(os.path.join(PROJECT_ROOT, "src"))

from nanobot.statistical_health_monitor import StatisticalHealthMonitor, get_health_monitor
from nanobot.utils.telegram_bot import TelegramBot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | 🤖 [AUTOPILOT] %(message)s'
)
logger = logging.getLogger("AUTOPILOT")

def run_autopilot_sync():
    """
    Analiza todos los pares con trades y aplica los veredictos estadísticos 
    al archivo governance.json si el piloto automático está habilitado.
    """
    logger.info("Starting Governance Autopilot Sync...")
    
    # Initialize monitor and bot
    monitor = get_health_monitor()
    tg_bot = TelegramBot()
    
    # Get all symbols that have trades
    symbols = set()
    for t in monitor.neme1_trades + monitor.neme2_trades:
        symbols.add(t.get("symbol"))
    
    if not symbols:
        logger.info("No trades found in history. Skipping sync.")
        return

    logger.info(f"Analyzing {len(symbols)} symbols...")
    
    updates = 0
    for symbol in symbols:
        # Check if autopilot is enabled for this symbol
        if not monitor.is_auto_pilot_enabled(symbol):
            continue
            
        # Get statistical verdict
        result = monitor.compare(symbol=symbol)
        
        current_pref = monitor.get_preference(symbol)
        
        # If we have a clear verdict and it's different from current
        if result.verdict in ["NEMESIS_1", "NEMESIS_2", "BOTH"] and result.verdict != current_pref:
            # We only apply if confidence is at least MEDIUM or it's a Heuristic Switch (Exploration)
            is_heuristic = "Explorer" in result.recommendation
            
            # [v6.2.0] PURIFICATION RULE: Use health scores for transitions
            if result.confidence in ["HIGH", "MEDIUM"] or is_heuristic:
                logger.info(f"🔄 AUTO-DECISION for {symbol}: {current_pref} -> {result.verdict}")
                logger.info(f"   Reason: {result.reason}")
                
                # Apply update
                monitor.set_preference(symbol, result.verdict)
                updates += 1

                # 📡 TELEGRAM MISSION REPORT
                if tg_bot.enabled:
                    # Get the relevant score for the new status
                    new_score = result.neme1_stats.health_score if result.verdict == "NEMESIS_1" else result.neme2_stats.health_score
                    tg_bot.send_health_update(
                        symbol=symbol,
                        old_status=f"Variant {current_pref}",
                        new_status=f"Healthy {result.verdict}",
                        score=new_score
                    )
            else:
                logger.info(f"⌛ Symbol {symbol} has verdict {result.verdict} but confidence is LOW. Staying with {current_pref}.")

    if updates > 0:
        logger.info(f"✅ Governance sync complete. Applied {updates} updates.")
    else:
        logger.info("✅ Governance sync complete. No changes needed.")

if __name__ == "__main__":
    run_autopilot_sync()
