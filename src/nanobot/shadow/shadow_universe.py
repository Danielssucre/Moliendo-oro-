"""
Shadow Universe - Paper Portfolio Manager
==========================================
DEPRECATED: Usar MegaGridV2 para ejecución real.
Este módulo se mantiene solo para backtesting histórico.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
from .shadow_engine import ShadowEngine, SimulatedTrade


@dataclass
class UniverseConfig:
    """Configuration for a universe."""

    name: str
    account_size: float
    lot_size: float
    sl_multiplier: float
    tp_multiplier: float


class ShadowUniverse:
    """
    Simula NEMESIS Dual en múltiples cuentas.

    NEMESIS 1: Dirección original
    NEMESIS 2: Dirección opuesta
    """

    ACCOUNTS = {
        "5K": 5000,
        "10K": 10000,
        "25K": 25000,
        "50K": 50000,
        "100K": 100000,
        "200K": 200000,
    }

    NEMESIS_CONFIG = {
        "sl": 1.5,
        "tp": 2.25,
    }

    NEMESIS_LOT = 0.03

    def __init__(self):
        self.universe_engines: Dict[str, ShadowEngine] = {}
        self.neme1_engines: Dict[str, ShadowEngine] = {}
        self.neme2_engines: Dict[str, ShadowEngine] = {}
        self._init_engines()

    def _init_engines(self):
        """Initialize one engine per account for each variant."""
        for acc_name in self.ACCOUNTS:
            neme1_name = f"{acc_name}_N1"
            neme2_name = f"{acc_name}_N2"
            self.neme1_engines[neme1_name] = ShadowEngine()
            self.neme2_engines[neme2_name] = ShadowEngine()
        self.universe_engines = self.neme1_engines.copy()

    def get_universes(self) -> List[str]:
        """Get list of all universe names."""
        return list(self.neme1_engines.keys())

    def get_config(self, universe: str) -> UniverseConfig:
        """Get configuration for a universe."""
        acc = universe.split("_")[0]
        acc_size = self.ACCOUNTS.get(acc, 10000)

        return UniverseConfig(
            name=universe,
            account_size=acc_size,
            lot_size=self.NEMESIS_LOT / 2,
            sl_multiplier=self.NEMESIS_CONFIG["sl"],
            tp_multiplier=self.NEMESIS_CONFIG["tp"],
        )

    def simulate_signal(
        self,
        signal_data: Dict,
        base_sl_pips: float,
        base_tp_pips: float,
        trade_id: str,
        neme_type: str = "NEMESIS_1",
    ) -> Dict[str, SimulatedTrade]:
        """
        Simulate NEMESIS signal across all universes.

        Args:
            signal_data: Dict with symbol, direction, entry_price, features
            base_sl_pips: Base SL in pips
            base_tp_pips: Base TP in pips
            trade_id: Unique trade ID
            neme_type: "NEMESIS_1" (original) or "NEMESIS_2" (opposite)

        Returns:
            Dict mapping universe_name -> SimulatedTrade
        """
        results = {}
        engines = self.neme1_engines if neme_type == "NEMESIS_1" else self.neme2_engines
        direction = signal_data["direction"]

        if neme_type == "NEMESIS_2":
            direction = -direction

        for universe in engines:
            config = self.get_config(universe)
            engine = engines[universe]

            sl_pips = base_sl_pips * config.sl_multiplier
            tp_pips = sl_pips * 1.5

            lot_size = self.NEMESIS_LOT / 2

            trade = engine.open_trade(
                symbol=signal_data["symbol"],
                strategy=neme_type,
                direction=direction,
                entry_price=signal_data["entry_price"],
                sl_pips=sl_pips,
                tp_pips=tp_pips,
                lot_size=lot_size,
                universe=universe,
                features=signal_data.get("features", {}),
                tf_info=signal_data.get("tf_info", {}),
                trade_id=f"{trade_id}_{universe}",
            )

            results[universe] = trade

        return results

    def simulate_dual(
        self, signal_data: Dict, base_sl_pips: float, base_tp_pips: float, trade_id: str
    ) -> Tuple[Dict[str, SimulatedTrade], Dict[str, SimulatedTrade]]:
        """
        Simulate BOTH NEMESIS 1 and NEMESIS 2 for the same signal.

        Returns:
            Tuple of (neme1_results, neme2_results)
        """
        neme1_results = self.simulate_signal(
            signal_data, base_sl_pips, base_tp_pips, trade_id, "NEMESIS_1"
        )
        neme2_results = self.simulate_signal(
            signal_data, base_sl_pips, base_tp_pips, trade_id, "NEMESIS_2"
        )
        return neme1_results, neme2_results

    def close_all_universes(self):
        """Force close all trades in all universes."""
        for engine in list(self.neme1_engines.values()) + list(
            self.neme2_engines.values()
        ):
            engine.close_all_trades()

    def get_all_stats(self) -> Dict:
        """Get combined statistics from all universes."""
        neme1_stats = {}
        neme2_stats = {}

        for universe, engine in self.neme1_engines.items():
            neme1_stats[universe] = engine.get_stats()

        for universe, engine in self.neme2_engines.items():
            neme2_stats[universe] = engine.get_stats()

        def combine(all_stats):
            combined = {}
            for acc in self.ACCOUNTS:
                acc_universes = [u for u in all_stats if u.startswith(acc)]
                if acc_universes:
                    combined[acc] = self._combine_stats(
                        [all_stats[u] for u in acc_universes]
                    )
            return combined

        return {
            "neme1": {
                "universes": neme1_stats,
                "by_account": combine(neme1_stats),
                "total": self._combine_stats(list(neme1_stats.values())),
            },
            "neme2": {
                "universes": neme2_stats,
                "by_account": combine(neme2_stats),
                "total": self._combine_stats(list(neme2_stats.values())),
            },
            "neme_config": self.NEMESIS_CONFIG,
            "neme_lot": self.NEMESIS_LOT,
        }

    def _combine_stats(self, stats_list: List[Dict]) -> Dict:
        """Combine stats from multiple universes."""
        if not stats_list:
            return {"total": 0, "wins": 0, "losses": 0}

        total = sum(s["total"] for s in stats_list)
        wins = sum(s["wins"] for s in stats_list)
        losses = sum(s["losses"] for s in stats_list)

        return {
            "total": total,
            "wins": wins,
            "losses": losses,
            "win_rate": wins / total if total > 0 else 0,
            "total_pnl": sum(s.get("total_pnl", 0) for s in stats_list),
            "avg_win": sum(s.get("avg_win", 0) for s in stats_list) / len(stats_list)
            if stats_list
            else 0,
            "avg_loss": sum(s.get("avg_loss", 0) for s in stats_list) / len(stats_list)
            if stats_list
            else 0,
        }

    def get_summary_dataframe(self):
        """Get combined summary of all universes."""
        import pandas as pd

        data = []

        for universe in self.neme1_engines:
            config = self.get_config(universe)
            stats = self.neme1_engines[universe].get_stats()

            data.append(
                {
                    "universe": universe,
                    "variant": "NEMESIS_1",
                    "account": universe.split("_")[0],
                    "strategy": "NEMESIS_1",
                    "account_size": config.account_size,
                    "sl_mult": config.sl_multiplier,
                    "tp_mult": config.tp_multiplier,
                    "lot_size": config.lot_size,
                    "total_trades": stats["total"],
                    "wins": stats["wins"],
                    "losses": stats["losses"],
                    "win_rate": stats["win_rate"],
                    "total_pnl": stats.get("total_pnl", 0),
                }
            )

        for universe in self.neme2_engines:
            config = self.get_config(universe)
            stats = self.neme2_engines[universe].get_stats()

            data.append(
                {
                    "universe": universe,
                    "variant": "NEMESIS_2",
                    "account": universe.split("_")[0],
                    "strategy": "NEMESIS_2",
                    "account_size": config.account_size,
                    "sl_mult": config.sl_multiplier,
                    "tp_mult": config.tp_multiplier,
                    "lot_size": config.lot_size,
                    "total_trades": stats["total"],
                    "wins": stats["wins"],
                    "losses": stats["losses"],
                    "win_rate": stats["win_rate"],
                    "total_pnl": stats.get("total_pnl", 0),
                }
            )

        return pd.DataFrame(data)
