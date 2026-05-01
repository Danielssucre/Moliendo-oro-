"""
Shadow Engine - Paper Trading Simulator
=====================================
DEPRECATED: Usar MegaGridV2 para ejecución real.
Este módulo se mantiene solo para backtesting histórico.
"""

import pandas as pd
import warnings
warnings.warn("ShadowEngine está deprecated. Usar MegaGridV2 para ejecución real.", DeprecationWarning)

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum


class ExitReason(Enum):
    """Reasons why a trade was closed."""

    TP_HIT = "TP"
    SL_HIT = "SL"
    TIMEOUT = "TIMEOUT"
    MANUAL = "MANUAL"
    PENDING = "PENDING"


@dataclass
class SimulatedTrade:
    """A simulated trade with all parameters and results."""

    # Identification
    trade_id: str
    symbol: str
    strategy: str
    timestamp: pd.Timestamp

    # Entry
    direction: int  # 1=BUY, -1=SELL
    entry_price: float

    # Parameters
    sl_pips: float
    tp_pips: float
    lot_size: float
    universe: str  # e.g., "B10K" (Balanced, $10K account)

    # Features at entry
    rsi: float
    adx: float
    atr_pct: float
    bb_deviation: float
    hour: int
    session: str
    regime: str
    ml_confidence: float

    # TF Escalation
    entry_tf: str
    confidence_score: float
    lot_multiplier: float

    # Results (filled when closed)
    exit_price: float = 0.0
    exit_reason: ExitReason = ExitReason.PENDING
    exit_timestamp: Optional[pd.Timestamp] = None
    pnl_pips: float = 0.0
    pnl_dollar: float = 0.0
    r_multiple: float = 0.0
    duration_hours: float = 0.0
    hit_tp: bool = False
    hit_sl: bool = False


class ShadowEngine:
    """
    Simulates trades paper-style.

    Takes entry signals and simulates SL/TP execution
    using historical price data.
    """

    PIP_VALUE_USD = {
        "EURUSD": 10.0,
        "GBPUSD": 10.0,
        "USDJPY": 9.0,  # Approximate
        "USDJPYmicro": 0.09,
        "AUDUSD": 10.0,
        "NZDUSD": 10.0,
        "USDCAD": 7.5,
        "EURAUD": 6.5,
        "GBPAUD": 6.5,
        "AUDJPY": 6.5,
        "GBPJPY": 6.5,
        "EURJPY": 8.5,
        "NZDJPY": 6.0,
        "CADJPY": 6.5,
        "AUDNZD": 6.0,
        "EURGBP": 10.0,
        "GBPCAD": 7.0,
        "CADCHF": 9.0,
        "XAUUSD": 100.0,
        "BTCUSD": 100.0,
        "ETHUSD": 10.0,
        "SOLUSD": 10.0,
    }

    def __init__(self, max_duration_hours: float = 72.0):
        self.active_trades: List[SimulatedTrade] = []
        self.closed_trades: List[SimulatedTrade] = []
        self.max_duration_hours = max_duration_hours

    def open_trade(
        self,
        symbol: str,
        strategy: str,
        direction: int,
        entry_price: float,
        sl_pips: float,
        tp_pips: float,
        lot_size: float,
        universe: str,
        features: Dict,
        tf_info: Dict,
        trade_id: str,
    ) -> SimulatedTrade:
        """Open a new simulated trade."""
        trade = SimulatedTrade(
            trade_id=trade_id,
            symbol=symbol,
            strategy=strategy,
            timestamp=pd.Timestamp.now(),
            direction=direction,
            entry_price=entry_price,
            sl_pips=sl_pips,
            tp_pips=tp_pips,
            lot_size=lot_size,
            universe=universe,
            rsi=features.get("rsi", 50),
            adx=features.get("adx", 20),
            atr_pct=features.get("atr_pct", 0),
            bb_deviation=features.get("bb_deviation", 0),
            hour=features.get("hour", 12),
            session=features.get("session", "UNKNOWN"),
            regime=features.get("regime", "UNKNOWN"),
            ml_confidence=features.get("ml_confidence", 0.5),
            entry_tf=tf_info.get("entry_tf", "H1"),
            confidence_score=tf_info.get("confidence_score", 0.5),
            lot_multiplier=tf_info.get("lot_multiplier", 1.0),
        )

        self.active_trades.append(trade)
        return trade

    def simulate_with_data(
        self, symbol: str, timeframe_data: pd.DataFrame, universe_config: Dict
    ) -> List[SimulatedTrade]:
        """
        Simulate all active trades using price data.

        Args:
            symbol: Trading symbol
            timeframe_data: OHLC data for simulation
            universe_config: SL/TP multipliers for this universe
        """
        results = []

        for trade in self.active_trades[:]:  # Copy to modify
            if trade.symbol != symbol:
                continue

            result = self._check_exit(trade, timeframe_data, universe_config)
            if result:
                results.append(result)
                self.active_trades.remove(trade)
                self.closed_trades.append(result)

        return results

    def _check_exit(
        self, trade: SimulatedTrade, data: pd.DataFrame, universe_config: Dict
    ) -> Optional[SimulatedTrade]:
        """Check if trade should exit based on price data."""
        if len(data) < 2:
            return None

        # Get entry index
        entry_time = trade.timestamp
        data_after_entry = data[data.index >= entry_time]

        if len(data_after_entry) < 2:
            return None

        high = data_after_entry["high"].values
        low = data_after_entry["low"].values
        close_arr = data_after_entry["close"].values
        open_arr = data_after_entry["open"].values

        entry = trade.entry_price
        sl = trade.sl_pips
        tp = trade.tp_pips

        # Calculate SL/TP prices
        if trade.direction == 1:  # BUY
            sl_price = entry - (sl * self._get_pip_size(trade.symbol))
            tp_price = entry + (tp * self._get_pip_size(trade.symbol))

            for i in range(1, len(close_arr)):
                current_price = close_arr[i]
                low_price = low[i]
                high_price = high[i]

                # Check TP first
                if high_price >= tp_price:
                    trade.exit_price = tp_price
                    trade.exit_reason = ExitReason.TP_HIT
                    trade.hit_tp = True
                    trade.exit_timestamp = data_after_entry.index[i]
                    break

                # Check SL
                if low_price <= sl_price:
                    trade.exit_price = sl_price
                    trade.exit_reason = ExitReason.SL_HIT
                    trade.hit_sl = True
                    trade.exit_timestamp = data_after_entry.index[i]
                    break

        else:  # SELL
            sl_price = entry + (sl * self._get_pip_size(trade.symbol))
            tp_price = entry - (tp * self._get_pip_size(trade.symbol))

            for i in range(1, len(close_arr)):
                current_price = close_arr[i]
                low_price = low[i]
                high_price = high[i]

                # Check TP first
                if low_price <= tp_price:
                    trade.exit_price = tp_price
                    trade.exit_reason = ExitReason.TP_HIT
                    trade.hit_tp = True
                    trade.exit_timestamp = data_after_entry.index[i]
                    break

                # Check SL
                if high_price >= sl_price:
                    trade.exit_price = sl_price
                    trade.exit_reason = ExitReason.SL_HIT
                    trade.hit_sl = True
                    trade.exit_timestamp = data_after_entry.index[i]
                    break

        # Calculate results if exited
        if trade.exit_reason != ExitReason.PENDING:
            self._calculate_results(trade, universe_config)
            return trade

        # Check timeout
        duration = (pd.Timestamp.now() - trade.timestamp).total_seconds() / 3600
        if duration > self.max_duration_hours:
            trade.exit_price = close_arr[-1]
            trade.exit_reason = ExitReason.TIMEOUT
            trade.exit_timestamp = data_after_entry.index[-1]
            self._calculate_results(trade, universe_config)
            return trade

        return None

    def _calculate_results(self, trade: SimulatedTrade, universe_config: Dict):
        """Calculate P&L and R-multiple."""
        pip_value = self._get_pip_value(trade.symbol)

        # Pips
        if trade.direction == 1:
            trade.pnl_pips = (
                trade.exit_price - trade.entry_price
            ) / self._get_pip_size(trade.symbol)
        else:
            trade.pnl_pips = (
                trade.entry_price - trade.exit_price
            ) / self._get_pip_size(trade.symbol)

        # Dollar P&L
        trade.pnl_dollar = trade.pnl_pips * pip_value * trade.lot_size

        # R-multiple (based on original SL)
        sl_pips_original = trade.sl_pips
        if sl_pips_original > 0:
            trade.r_multiple = trade.pnl_pips / sl_pips_original
        else:
            trade.r_multiple = 0

        # Duration
        if trade.exit_timestamp:
            trade.duration_hours = (
                trade.exit_timestamp - trade.timestamp
            ).total_seconds() / 3600
        else:
            trade.duration_hours = 0

    def _get_pip_size(self, symbol: str) -> float:
        """Get pip size for symbol."""
        if "JPY" in symbol:
            return 0.01
        return 0.0001

    def _get_pip_value(self, symbol: str) -> float:
        """Get pip value in USD for 1 lot."""
        # Try exact match
        if symbol in self.PIP_VALUE_USD:
            return self.PIP_VALUE_USD[symbol]

        # Try partial match
        for key, value in self.PIP_VALUE_USD.items():
            if key in symbol:
                return value

        return 10.0  # Default for majors

    def close_all_trades(self, reason: ExitReason = ExitReason.MANUAL):
        """Force close all active trades."""
        for trade in self.active_trades[:]:
            trade.exit_price = trade.entry_price  # Assume no movement
            trade.exit_reason = reason
            trade.exit_timestamp = pd.Timestamp.now()
            self._calculate_results(trade, {})
            self.closed_trades.append(trade)

        self.active_trades.clear()

    def get_stats(self) -> Dict:
        """Get statistics from all closed trades."""
        if not self.closed_trades:
            return {
                "total": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "expectancy": 0,
            }

        wins = [t for t in self.closed_trades if t.pnl_dollar > 0]
        losses = [t for t in self.closed_trades if t.pnl_dollar <= 0]

        total_wins = len(wins)
        total_losses = len(losses)
        total = len(self.closed_trades)

        avg_win = np.mean([t.pnl_dollar for t in wins]) if wins else 0
        avg_loss = abs(np.mean([t.pnl_dollar for t in losses])) if losses else 0

        total_win_pnl = sum(t.pnl_dollar for t in wins)
        total_loss_pnl = abs(sum(t.pnl_dollar for t in losses))

        profit_factor = total_win_pnl / total_loss_pnl if total_loss_pnl > 0 else 0

        win_rate = total_wins / total if total > 0 else 0
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

        return {
            "total": total,
            "wins": total_wins,
            "losses": total_losses,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "active": len(self.active_trades),
            "total_pnl": sum(t.pnl_dollar for t in self.closed_trades),
        }

    def get_trades_dataframe(self) -> pd.DataFrame:
        """Get all closed trades as DataFrame."""
        if not self.closed_trades:
            return pd.DataFrame()

        data = []
        for t in self.closed_trades:
            data.append(
                {
                    "trade_id": t.trade_id,
                    "timestamp": t.timestamp,
                    "symbol": t.symbol,
                    "strategy": t.strategy,
                    "direction": "BUY" if t.direction == 1 else "SELL",
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "exit_reason": t.exit_reason.value,
                    "pnl_pips": t.pnl_pips,
                    "pnl_dollar": t.pnl_dollar,
                    "r_multiple": t.r_multiple,
                    "duration_hours": t.duration_hours,
                    "universe": t.universe,
                    "entry_tf": t.entry_tf,
                    "confidence_score": t.confidence_score,
                    "lot_multiplier": t.lot_multiplier,
                    "rsi": t.rsi,
                    "adx": t.adx,
                    "hour": t.hour,
                    "session": t.session,
                    "regime": t.regime,
                }
            )

        return pd.DataFrame(data)
