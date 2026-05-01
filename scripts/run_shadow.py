#!/usr/bin/env python3
"""
Shadow System Standalone - Recolector de Datos
=============================================
Script para ejecutar junto con run_live.py.
Se conecta al proceso y recolecta señales para los 30 universos.

Uso:
    python3 scripts/run_shadow.py

El script monitorea las señales del sistema y las replica en universos.
"""

import sys
import os
import time
import signal
import logging
from datetime import datetime
from pathlib import Path

# Add project to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/shadow_{datetime.now().strftime('%Y%m%d')}.log"),
    ],
)
logger = logging.getLogger("ShadowStandalone")


class ShadowCollector:
    """
    Recolector standalone que monitorea y replica señales.

    Puede ejecutarse de forma independiente o junto con run_live.py.
    """

    def __init__(self):
        self.running = True
        self.trades_logged = 0

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Import shadow components
        try:
            from nanobot.shadow import (
                ShadowUniverse,
                ShadowLogger,
                MultiTimeframeEscalator,
            )

            self.universe = ShadowUniverse()
            self.logger = ShadowLogger(daily_rotation=True)
            self.escalator = MultiTimeframeEscalator()
            self.shadow_available = True
            logger.info("✅ Shadow components loaded")
        except ImportError as e:
            logger.error(f"❌ Shadow components not available: {e}")
            self.shadow_available = False
            return

        logger.info(f"🌙 Shadow Collector initialized")
        logger.info(f"   Universes: {len(self.universe.get_universes())}")
        logger.info(f"   Log file: {self.logger.current_file}")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("🛑 Shutdown signal received...")
        self.running = False

    def log_signal(
        self,
        symbol: str,
        strategy: str,
        direction: int,
        entry_price: float,
        features: dict,
    ):
        """
        Log a signal and simulate across all universes.

        Args:
            symbol: Trading symbol
            strategy: Strategy name
            direction: 1=BUY, -1=SELL
            entry_price: Entry price
            features: Dict with rsi, adx, atr_pct, etc.
        """
        if not self.shadow_available:
            return None

        from nanobot.shadow import ShadowEngine

        trade_id = f"{symbol}_{int(time.time())}"

        # Calculate base SL/TP
        base_sl = features.get("sl_pips", 30)
        base_tp = features.get("tp_pips", 75)

        # Prepare signal
        signal_data = {
            "symbol": symbol,
            "strategy": strategy,
            "direction": direction,
            "entry_price": entry_price,
            "features": features,
            "tf_info": {
                "entry_tf": features.get("entry_tf", "H1"),
                "confidence_score": features.get("ml_confidence", 0.5),
                "lot_multiplier": features.get("lot_multiplier", 1.0),
            },
        }

        # Simulate across all universes
        try:
            results = self.universe.simulate_signal(
                signal_data=signal_data,
                base_sl_pips=base_sl,
                base_tp_pips=base_tp,
                trade_id=trade_id,
            )

            # Log to CSV
            for universe_name, trade in results.items():
                self.logger.log_trade(
                    {
                        "trade_id": trade_id,
                        "universe": universe_name,
                        "timestamp": datetime.now().isoformat(),
                        "symbol": symbol,
                        "strategy": strategy,
                        "direction": "BUY" if direction == 1 else "SELL",
                        "entry_price": entry_price,
                        "sl_pips": trade.sl_pips,
                        "tp_pips": trade.tp_pips,
                        "lot_size": trade.lot_size,
                        "rsi": features.get("rsi", 0),
                        "adx": features.get("adx", 0),
                        "atr_pct": features.get("atr_pct", 0),
                        "hour": features.get("hour", datetime.now().hour),
                        "ml_confidence": features.get("ml_confidence", 0),
                        "entry_tf": features.get("entry_tf", "H1"),
                        "confidence_score": features.get("ml_confidence", 0.5),
                        "status": "OPEN",
                    }
                )

            self.trades_logged += 1
            self.logger.flush()

            logger.info(
                f"🌙 Signal logged: {symbol} | {strategy} | "
                f"{len(results)} universes | Total: {self.trades_logged}"
            )

            return trade_id

        except Exception as e:
            logger.error(f"❌ Error logging signal: {e}")
            return None

    def simulate_closed_trade(
        self,
        trade_id: str,
        symbol: str,
        direction: int,
        entry_price: float,
        exit_price: float,
        exit_reason: str,
        duration_hours: float = 0,
    ):
        """
        Simula el cierre de un trade en todos los universos.

        Args:
            trade_id: Original trade ID
            symbol: Trading symbol
            direction: 1=BUY, -1=SELL
            entry_price: Entry price
            exit_price: Exit price
            exit_reason: TP, SL, MANUAL, TIMEOUT
            duration_hours: Trade duration
        """
        if not self.shadow_available:
            return

        # Calculate results
        pip_size = 0.01 if "JPY" in symbol else 0.0001

        if direction == 1:
            pnl_pips = (exit_price - entry_price) / pip_size
        else:
            pnl_pips = (entry_price - exit_price) / pip_size

        # Log closed trade (would need actual simulation to get per-universe results)
        logger.info(
            f"📊 Trade closed: {symbol} | {exit_reason} | "
            f"{pnl_pips:.1f} pips | {duration_hours:.1f}h"
        )

    def run_demo(self, num_signals: int = 5):
        """
        Ejecuta una demo con señales simuladas.

        Args:
            num_signals: Number of fake signals to generate
        """
        if not self.shadow_available:
            logger.error("Shadow not available")
            return

        logger.info(f"🧪 Running demo with {num_signals} signals...")

        symbols = ["GBPAUD", "AUDJPY", "EURUSD", "GBPJPY", "EURAUD"]
        strategies = ["CHAMPION", "NEMESIS"]

        for i in range(num_signals):
            symbol = symbols[i % len(symbols)]
            strategy = strategies[i % len(strategies)]
            direction = 1 if i % 2 == 0 else -1
            entry = 2.0500 + (i * 0.001)

            features = {
                "rsi": 70 + (i * 2),
                "adx": 20 + (i * 2),
                "atr_pct": 0.001 + (i * 0.0001),
                "hour": 14 + (i % 4),
                "ml_confidence": 0.5 + (i * 0.05),
                "sl_pips": 30,
                "tp_pips": 75,
                "entry_tf": "H1",
                "lot_multiplier": 1.0,
            }

            self.log_signal(symbol, strategy, direction, entry, features)
            time.sleep(0.5)

        logger.info("✅ Demo complete")
        self.print_stats()

    def print_stats(self):
        """Print current statistics."""
        if not self.shadow_available:
            return

        stats = self.logger.get_summary()

        print()
        print("=" * 60)
        print("🌙 SHADOW COLLECTOR STATS")
        print("=" * 60)
        print(f"  Signals logged: {self.trades_logged}")
        print(f"  Log file: {stats.get('file', 'N/A')}")
        print(f"  Total trades: {stats.get('total_trades', 0)}")
        print(f"  Universes: {stats.get('universes', 0)}")
        print("=" * 60)
        print()

    def start(self):
        """Start the shadow collector."""
        logger.info("🚀 Shadow Collector starting...")

        # Run demo first
        self.run_demo(num_signals=3)

        print()
        print("📋 INTEGRATION INSTRUCTIONS")
        print("-" * 60)
        print("""
To integrate with run_live.py, add this after ML Filter passes:

    from src.nanobot.shadow import get_shadow_integrator
    
    shadow = get_shadow_integrator()
    if shadow.enabled:
        shadow.on_signal_accepted(
            symbol=symbol,
            strategy=strategy,
            direction=sig,
            entry_price=row['close'],
            features={
                'rsi': rsi,
                'adx': adx,
                'atr_pct': atr/close if close > 0 else 0,
                'hour': current_hour,
                'ml_confidence': ml_conf,
                'sl_pips': 30,
                'tp_pips': 75
            }
        )

Or set environment variable: export SHADOW_ENABLED=true
        """)
        print("-" * 60)
        print()

        # Keep running
        logger.info("💡 Shadow Collector ready. Waiting for signals...")
        logger.info("   Press Ctrl+C to exit")

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

        self.shutdown()

    def shutdown(self):
        """Cleanup and exit."""
        logger.info("🛑 Shutting down...")

        if self.shadow_available and self.logger:
            self.logger.flush()
            self.logger.close()

        self.print_stats()
        logger.info("✅ Shutdown complete")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Shadow Collector")
    parser.add_argument("--demo", action="store_true", help="Run demo mode")
    parser.add_argument("--signals", type=int, default=3, help="Demo signals")
    args = parser.parse_args()

    collector = ShadowCollector()

    if args.demo:
        collector.run_demo(num_signals=args.signals)
    else:
        collector.start()


if __name__ == "__main__":
    main()
