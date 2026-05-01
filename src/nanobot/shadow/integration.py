"""
Shadow Integration - NEMESIS Dual System
======================================
Integrates shadow simulation with Statistical Health Monitor for NEMESIS 1 vs NEMESIS 2.

Features:
- Simulates both NEMESIS 1 and NEMESIS 2 in shadow
- Integrates with Statistical Health Monitor
- Logs trades for both variants
- Provides decision support for live trading
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Optional, Tuple
import uuid
import json
import os

try:
    from nanobot.shadow import (
        ShadowEngine,
        ShadowUniverse,
        ShadowLogger,
    )

    SHADOW_AVAILABLE = True
except ImportError:
    SHADOW_AVAILABLE = False
    print("⚠️ Shadow components not available")

try:
    from nanobot.statistical_health_monitor import StatisticalHealthMonitor

    STATISTICAL_AVAILABLE = True
except ImportError:
    STATISTICAL_AVAILABLE = False
    print("⚠️ Statistical Health Monitor not available")


class NemesisDualIntegrator:
    """
    Integrates NEMESIS Dual system with Shadow simulation and Statistical Health Monitor.

    Flow:
    1. Signal generated
    2. Simulate BOTH NEMESIS 1 and NEMESIS 2 in shadow
    3. When trades close, log results to Health Monitor
    4. Periodically run statistical comparison
    5. Report which variant is performing better
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled and SHADOW_AVAILABLE
        self.statistical_enabled = enabled and STATISTICAL_AVAILABLE

        if self.enabled:
            self.universe = ShadowUniverse()
            self.logger = ShadowLogger(base_path="data/shadow", daily_rotation=True)
            print("🌙 NEMESIS DUAL: Shadow ENABLED")
            print(f"   Universes: {len(self.universe.get_universes())} per variant")

        if self.statistical_enabled:
            self.health_monitor = StatisticalHealthMonitor(
                config_path="config/statistical_config.json"
            )
            print("📊 NEMESIS DUAL: Statistical Health Monitor ENABLED")

        if not self.enabled:
            self.universe = None
            self.logger = None
            print("🌙 NEMESIS DUAL: DISABLED")

        if not self.statistical_enabled:
            self.health_monitor = None

        self.registry_path = "data/shadow/mt5_trade_registry.json"
        self.mt5_trade_registry = {}
        
        if self.enabled:
            self._load_registry()
    def _load_registry(self):
        """Load the trade registry from disk."""
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r") as f:
                    data = json.load(f)
                    # JSON keys are always strings, convert back to int tickets
                    self.mt5_trade_registry = {int(k): v for k, v in data.items()}
                    print(f"🌙 [SHADOW] Loaded {len(self.mt5_trade_registry)} trades from registry.")
            except Exception as e:
                print(f"⚠️ Could not load shadow registry: {e}")

    def _save_registry(self):
        """Save the trade registry to disk."""
        try:
            os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
            with open(self.registry_path, "w") as f:
                json.dump(self.mt5_trade_registry, f, indent=4)
        except Exception as e:
            print(f"❌ Could not save shadow registry: {e}")

    def on_mt5_trade_opened(
        self,
        ticket: int,
        symbol: str,
        strategy: str,
        entry_price: float,
        direction: int,
        sl: float = None,
        tp: float = None,
    ) -> bool:
        """
        Registrar que un trade se abrió en MT5 real.

        Args:
            ticket: Ticket de MT5
            symbol: Par de trading
            strategy: Estrategia (NEMESIS_1, NEMESIS_2, etc.)
            entry_price: Precio de entrada
            direction: 1=BUY, -1=SELL
            sl: Stop Loss price
            tp: Take Profit price

        Returns:
            True si se registró correctamente
        """
        if not self.enabled:
            return False

        self.mt5_trade_registry[ticket] = {
            "symbol": symbol,
            "strategy": strategy,
            "direction": direction,
            "entry_price": entry_price,
            "sl": sl,
            "tp": tp,
            "opened_at": datetime.now().isoformat() if isinstance(datetime.now(), datetime) else datetime.now(),
            "status": "OPEN",
        }
        
        self._save_registry()

        print(f"🌙 [SHADOW SYNC] MT5 trade opened: #{ticket} {symbol} {strategy}")
        return True

    def on_signal_accepted(
        self,
        symbol: str,
        strategy: str,
        direction: int,
        entry_price: float,
        features: Dict,
    ) -> Optional[str]:
        """
        Handle a signal that was accepted for execution.
        This is the main entry point called from run_live.py.

        Args:
            symbol: Trading pair
            strategy: Strategy name (e.g., "NEMESIS_1", "NEMESIS_2")
            direction: Signal direction (1=BUY, -1=SELL)
            entry_price: Entry price
            features: Dict with rsi, adx, atr_pct, etc.

        Returns:
            Trade ID or None
        """
        if not self.enabled:
            return None

        trade_id = str(uuid.uuid4())[:8]
        sl_pips = features.get("sl_pips", 30)
        tp_pips = features.get("tp_pips", 75)

        signal_data = {
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "features": features,
            "tf_info": {
                "entry_tf": features.get("entry_tf", "H1"),
                "confidence_score": features.get("ml_confidence", 0.5),
                "lot_multiplier": features.get("lot_multiplier", 1.0),
            },
        }

        try:
            if strategy in ["NEMESIS_1", "NEMESIS_2"]:
                neme_type = strategy
                neme1_results, neme2_results = self.universe.simulate_dual(
                    signal_data=signal_data,
                    base_sl_pips=sl_pips,
                    base_tp_pips=tp_pips,
                    trade_id=trade_id,
                )

                self._log_dual_trades(
                    trade_id=trade_id,
                    symbol=symbol,
                    direction=direction,
                    entry_price=entry_price,
                    features=features,
                    neme1_results=neme1_results,
                    neme2_results=neme2_results,
                )

                self.trades_count += 1
                print(
                    f"🌙 NEMESIS DUAL: {symbol} | {strategy} | N1:{len(neme1_results)} | N2:{len(neme2_results)} universes"
                )
                return trade_id
            else:
                return None

        except Exception as e:
            print(f"❌ NEMESIS DUAL error: {e}")
            return None

    def on_signal(
        self,
        symbol: str,
        direction: int,
        entry_price: float,
        features: Dict,
        live_neme1: bool = True,
        live_neme2: bool = False,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Handle a new NEMESIS signal - simulate both variants.
        Legacy method for backwards compatibility.

        Args:
            symbol: Trading pair
            direction: Original signal direction (1=BUY, -1=SELL)
            entry_price: Entry price
            features: Dict with rsi, adx, atr_pct, etc.
            live_neme1: If True, NEMESIS 1 should go live
            live_neme2: If True, NEMESIS 2 should go live

        Returns:
            Tuple of (neme1_trade_id, neme2_trade_id)
        """
        if not self.enabled:
            return None, None

        trade_id = str(uuid.uuid4())[:8]

        sl_pips = features.get("sl_pips", 30)
        tp_pips = features.get("tp_pips", 75)

        signal_data = {
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "features": features,
            "tf_info": {
                "entry_tf": features.get("entry_tf", "H1"),
                "confidence_score": features.get("ml_confidence", 0.5),
                "lot_multiplier": features.get("lot_multiplier", 1.0),
            },
        }

        try:
            neme1_results, neme2_results = self.universe.simulate_dual(
                signal_data=signal_data,
                base_sl_pips=sl_pips,
                base_tp_pips=tp_pips,
                trade_id=trade_id,
            )

            self._log_dual_trades(
                trade_id=trade_id,
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                features=features,
                neme1_results=neme1_results,
                neme2_results=neme2_results,
            )

            self.trades_count += 1

            print(
                f"🌙 NEMESIS DUAL: {symbol} | N1:{len(neme1_results)} | N2:{len(neme2_results)} universes"
            )

            return trade_id, trade_id

        except Exception as e:
            print(f"❌ NEMESIS DUAL error: {e}")
            return None, None

    def _log_dual_trades(
        self,
        trade_id: str,
        symbol: str,
        direction: int,
        entry_price: float,
        features: Dict,
        neme1_results: Dict,
        neme2_results: Dict,
    ):
        """Log both NEMESIS 1 and NEMESIS 2 trades."""
        timestamp = datetime.now().isoformat()

        for universe_name, trade in neme1_results.items():
            self.logger.log_trade(
                {
                    "trade_id": trade_id,
                    "universe": universe_name,
                    "timestamp": timestamp,
                    "symbol": symbol,
                    "strategy": "NEMESIS_1",
                    "variant": "NEMESIS_1",
                    "direction": "BUY" if direction == 1 else "SELL",
                    "original_direction": direction,
                    "entry_price": entry_price,
                    "sl_pips": trade.sl_pips,
                    "tp_pips": trade.tp_pips,
                    "lot_size": trade.lot_size,
                    "rsi": features.get("rsi", 0),
                    "adx": features.get("adx", 0),
                    "atr_pct": features.get("atr_pct", 0),
                    "hour": features.get("hour", 0),
                    "ml_confidence": features.get("ml_confidence", 0),
                    "entry_tf": features.get("entry_tf", "H1"),
                    "status": "OPEN",
                }
            )

        for universe_name, trade in neme2_results.items():
            self.logger.log_trade(
                {
                    "trade_id": trade_id,
                    "universe": universe_name,
                    "timestamp": timestamp,
                    "symbol": symbol,
                    "strategy": "NEMESIS_2",
                    "variant": "NEMESIS_2",
                    "direction": "SELL" if direction == 1 else "BUY",
                    "original_direction": direction,
                    "entry_price": entry_price,
                    "sl_pips": trade.sl_pips,
                    "tp_pips": trade.tp_pips,
                    "lot_size": trade.lot_size,
                    "rsi": features.get("rsi", 0),
                    "adx": features.get("adx", 0),
                    "atr_pct": features.get("atr_pct", 0),
                    "hour": features.get("hour", 0),
                    "ml_confidence": features.get("ml_confidence", 0),
                    "entry_tf": features.get("entry_tf", "H1"),
                    "status": "OPEN",
                }
            )

        self.logger.flush()

    def on_trade_closed(
        self,
        ticket: int = None,
        trade_id: str = None,
        variant: str = None,
        pnl_dollar: float = 0.0,
        pnl_pips: float = 0.0,
        exit_reason: str = "UNKNOWN",
        duration_hours: float = 0.0,
        symbol: str = None,
    ):
        """
        Registrar que un trade se cerró.

        Args:
            ticket: Ticket de MT5 (para buscar en registry)
            trade_id: ID interno del trade
            variant: Estrategia (NEMESIS_1, NEMESIS_2)
            pnl_dollar: P&L en dólares
            pnl_pips: P&L en pips
            exit_reason: Razón del cierre (TP, SL, MT5_CLOSE, TIMEOUT)
            duration_hours: Duración en horas
            symbol: Par de trading

        Returns:
            True si se registró correctamente
        """
        if not self.statistical_enabled or not self.health_monitor:
            return False

        resolved_variant = variant
        resolved_symbol = symbol

        if ticket and hasattr(self, "mt5_trade_registry"):
            registry = self.mt5_trade_registry
            if ticket in registry:
                trade_info = registry[ticket]
                resolved_variant = resolved_variant or trade_info.get("strategy")
                resolved_symbol = resolved_symbol or trade_info.get("symbol")
                registry[ticket]["status"] = "CLOSED"
                self._save_registry()

        if not resolved_variant:
            print(f"⚠️ [SHADOW] Cannot close trade: no strategy specified")
            return False

        if "NEMESIS_1" in resolved_variant:
            final_variant = "NEMESIS_1"
        elif "NEMESIS_2" in resolved_variant:
            final_variant = "NEMESIS_2"
        else:
            final_variant = resolved_variant

        self.health_monitor.add_trade(
            variant=final_variant,
            profit=pnl_dollar,
            is_win=pnl_dollar > 0,
            symbol=resolved_symbol,
            ticket=ticket,
            trade_id=trade_id,
            pips=pnl_pips,
            exit_reason=exit_reason,
            duration_hours=duration_hours,
        )

        print(
            f"📊 [HEALTH MONITOR] Trade closed: {final_variant} | "
            f"P&L: ${pnl_dollar:+.2f} | {'WIN' if pnl_dollar > 0 else 'LOSS'}"
        )

        return True

    def should_run_comparison(self) -> bool:
        """Check if we should run a statistical comparison."""
        if not self.statistical_enabled or not self.health_monitor:
            return False

        summary = self.health_monitor.get_summary()
        current_trades = summary.get("neme1_trades", 0) + summary.get("neme2_trades", 0)

        if current_trades - self.last_comparison_trades >= 10:
            return True
        return False

    def run_comparison(self) -> Optional[Dict]:
        """
        Run statistical comparison of NEMESIS 1 vs NEMESIS 2.

        Returns:
            Comparison result dict or None if insufficient data
        """
        if not self.statistical_enabled or not self.health_monitor:
            return None

        summary = self.health_monitor.get_summary()

        if summary.get("status") == "INSUFFICIENT_DATA":
            return None

        result = self.health_monitor.compare()

        self.last_comparison_trades = summary.get("neme1_trades", 0) + summary.get(
            "neme2_trades", 0
        )

        self._save_comparison_result(result)

        return {
            "verdict": result.verdict,
            "confidence": result.confidence,
            "p_value": result.p_value_ttest,
            "neme1_stats": {
                "trades": result.neme1_stats.trades,
                "win_rate": result.neme1_stats.win_rate,
                "total_pnl": result.neme1_stats.total_pnl,
                "mean_profit": result.neme1_stats.mean_profit,
            },
            "neme2_stats": {
                "trades": result.neme2_stats.trades,
                "win_rate": result.neme2_stats.win_rate,
                "total_pnl": result.neme2_stats.total_pnl,
                "mean_profit": result.neme2_stats.mean_profit,
            },
            "recommendation": result.recommendation,
        }

    def _save_comparison_result(self, result):
        """Save comparison result to file."""
        os.makedirs("logs", exist_ok=True)
        result_file = "logs/nemesis_health.jsonl"

        with open(result_file, "a") as f:
            f.write(
                json.dumps(
                    {
                        "timestamp": result.timestamp,
                        "verdict": result.verdict,
                        "confidence": result.confidence,
                        "p_value": result.p_value_ttest,
                        "effect_size": result.cohens_d,
                        "neme1": {
                            "trades": result.neme1_stats.trades,
                            "win_rate": result.neme1_stats.win_rate,
                            "total_pnl": result.neme1_stats.total_pnl,
                            "mean_profit": result.neme1_stats.mean_profit,
                        },
                        "neme2": {
                            "trades": result.neme2_stats.trades,
                            "win_rate": result.neme2_stats.win_rate,
                            "total_pnl": result.neme2_stats.total_pnl,
                            "mean_profit": result.neme2_stats.mean_profit,
                        },
                    }
                )
                + "\n"
            )

    def get_preferred_variant(self, symbol: str = None) -> str:
        """Get the preferred variant based on Health Monitor decisions."""
        if self.statistical_enabled and self.health_monitor:
            return self.health_monitor.get_preference(symbol)
        return "BOTH"

    def get_summary(self) -> Dict:
        """Get summary of current state."""
        summary = {
            "enabled": self.enabled,
            "statistical_enabled": self.statistical_enabled,
            "trades_count": self.trades_count,
        }

        if self.statistical_enabled and self.health_monitor:
            summary["health"] = self.health_monitor.get_summary()

        return summary

    def flush(self):
        """Flush pending data to disk."""
        if self.logger:
            self.logger.flush()

    def close(self):
        """Close and cleanup."""
        if self.logger:
            self.logger.close()


_shadow_integrator = None


def get_shadow_integrator(enabled: bool = True) -> NemesisDualIntegrator:
    """Get or create the global shadow integrator."""
    global _shadow_integrator

    if _shadow_integrator is None:
        _shadow_integrator = NemesisDualIntegrator(enabled=enabled)

    return _shadow_integrator


if __name__ == "__main__":
    print("Testing NEMESIS Dual Integrator...\n")

    integrator = get_shadow_integrator(enabled=True)

    if integrator.enabled:
        print("\nSimulating a dual signal...")

        integrator.on_signal(
            symbol="EURUSD",
            direction=1,
            entry_price=1.1850,
            features={
                "rsi": 78.5,
                "adx": 25.3,
                "atr_pct": 0.0012,
                "hour": 15,
                "ml_confidence": 0.65,
                "sl_pips": 30,
                "tp_pips": 75,
            },
        )

        print(f"\nSummary: {integrator.get_summary()}")

        integrator.flush()

    print("\n✅ NEMESIS Dual Integrator test complete")
