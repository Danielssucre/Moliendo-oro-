"""
Shadow Logger - NEMESIS Data Collection
======================================
Recolecta datos de simulación NEMESIS para análisis y re-entrenamiento.

NEMESIS 4898079:
- Strategy: NEMESIS (inversión de CHAMPION)
- RR: 1.5
- SL: ATR × 1.5
- TP: ATR × 2.25
- Lot: 0.03 fijo
- Time: 24/7
"""

import pandas as pd
import os
from datetime import datetime
from typing import Dict, List
from pathlib import Path


class ShadowLogger:
    """
    Logger para recolectar datos NEMESIS.

    Guarda en CSV:
    - Una fila por trade por universo
    - Features completas para ML
    - Resultados para análisis
    """

    def __init__(self, base_path: str = "data/shadow", daily_rotation: bool = True):
        """
        Initialize shadow logger.

        Args:
            base_path: Base directory for CSV files
            daily_rotation: If True, create new file each day
        """
        self.base_path = Path(base_path)
        self.daily_rotation = daily_rotation
        self.buffer: List[Dict] = []
        self.buffer_size = 100  # Flush every 100 trades
        self.session_start = datetime.now()

        # Create directory if not exists
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Get current file path
        self.current_file = self._get_file_path()

        # Load existing data if file exists
        self._load_existing()

    def _get_file_path(self) -> Path:
        """Get the current CSV file path."""
        if self.daily_rotation:
            date_str = datetime.now().strftime("%Y%m%d")
            return self.base_path / f"shadow_signals_{date_str}.csv"
        else:
            return self.base_path / "shadow_signals.csv"

    def _load_existing(self):
        """Load existing data if file exists."""
        if self.current_file.exists():
            try:
                self._existing_df = pd.read_csv(self.current_file)
                print(
                    f"📊 Shadow Logger: Loaded {len(self._existing_df)} existing trades"
                )
            except Exception as e:
                print(f"⚠️ Could not load existing file: {e}")
                self._existing_df = pd.DataFrame()
        else:
            self._existing_df = pd.DataFrame()

    def log_trade(self, trade_data: Dict):
        """
        Log a single trade result.

        Args:
            trade_data: Dictionary with trade information
        """
        self.buffer.append(trade_data)

        if len(self.buffer) >= self.buffer_size:
            self.flush()

    def log_batch(self, trades: List[Dict]):
        """Log multiple trades at once."""
        self.buffer.extend(trades)

        if len(self.buffer) >= self.buffer_size:
            self.flush()

    def log_signal(self, signal_data: Dict):
        """
        Log an incoming signal (before result is known).

        Args:
            signal_data: Dictionary with signal features
        """
        # Add metadata
        signal_data["_logged_at"] = datetime.now().isoformat()
        signal_data["_session_id"] = self.session_start.strftime("%Y%m%d_%H%M%S")

        self.log_trade(signal_data)

    def log_closed_trade(self, trade_id: str, universe: str, result: Dict):
        """
        Log closed trade result.

        Args:
            trade_id: Original trade ID
            universe: Universe name
            result: Trade result dictionary
        """
        result_data = {
            "trade_id": trade_id,
            "universe": universe,
            "_result_logged_at": datetime.now().isoformat(),
            **result,
        }

        self.log_trade(result_data)

    def flush(self):
        """Write buffer to CSV file."""
        if not self.buffer:
            return

        # Convert to DataFrame
        new_df = pd.DataFrame(self.buffer)

        # Append to existing
        if self._existing_df is not None and len(self._existing_df) > 0:
            combined_df = pd.concat([self._existing_df, new_df], ignore_index=True)
        else:
            combined_df = new_df

        # Write to CSV
        try:
            combined_df.to_csv(self.current_file, index=False)
            print(
                f"💾 Shadow Logger: Flushed {len(self.buffer)} trades to {self.current_file.name}"
            )
            print(f"   Total trades: {len(combined_df)}")
        except Exception as e:
            print(f"❌ Error writing to CSV: {e}")
            # Try to write just the new buffer
            try:
                new_df.to_csv(self.current_file.with_suffix(".new.csv"), index=False)
            except:
                pass

        # Clear buffer
        self.buffer.clear()
        self._existing_df = combined_df

    def get_dataframe(self) -> pd.DataFrame:
        """Get all logged data as DataFrame."""
        if self._existing_df is not None and len(self._existing_df) > 0:
            return self._existing_df.copy()
        return pd.DataFrame()

    def get_summary(self) -> Dict:
        """Get summary statistics from logged data."""
        df = self.get_dataframe()

        if df.empty:
            return {"total_trades": 0, "universes": 0, "symbols": 0, "strategies": 0}

        summary = {
            "total_trades": len(df),
            "universes": df["universe"].nunique() if "universe" in df.columns else 0,
            "symbols": df["symbol"].nunique() if "symbol" in df.columns else 0,
            "strategies": df["strategy"].nunique() if "strategy" in df.columns else 0,
            "session_start": self.session_start.isoformat(),
            "file": str(self.current_file),
        }

        # Add results if available
        if "pnl_dollar" in df.columns:
            wins = df[df["pnl_dollar"] > 0]
            losses = df[df["pnl_dollar"] <= 0]

            summary.update(
                {
                    "wins": len(wins),
                    "losses": len(losses),
                    "win_rate": len(wins) / len(df) if len(df) > 0 else 0,
                    "total_pnl": df["pnl_dollar"].sum(),
                    "avg_win": wins["pnl_dollar"].mean() if len(wins) > 0 else 0,
                    "avg_loss": losses["pnl_dollar"].mean() if len(losses) > 0 else 0,
                }
            )

        return summary

    def get_universe_summary(self) -> pd.DataFrame:
        """Get summary grouped by universe."""
        df = self.get_dataframe()

        if df.empty or "universe" not in df.columns:
            return pd.DataFrame()

        summary = (
            df.groupby("universe")
            .agg(
                {
                    "pnl_dollar": ["count", "sum", "mean"]
                    if "pnl_dollar" in df.columns
                    else ["count"],
                    "r_multiple": "mean" if "r_multiple" in df.columns else "count",
                    "duration_hours": "mean"
                    if "duration_hours" in df.columns
                    else "count",
                }
            )
            .round(2)
        )

        return summary

    def export_all(self, output_dir: str = None):
        """
        Export all data to separate CSV files.

        Args:
            output_dir: Optional output directory
        """
        if output_dir:
            export_path = Path(output_dir)
        else:
            export_path = self.base_path / "exports"

        export_path.mkdir(parents=True, exist_ok=True)

        df = self.get_dataframe()

        if df.empty:
            print("⚠️ No data to export")
            return

        # Export full dataset
        full_path = (
            export_path / f"all_shadows_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        df.to_csv(full_path, index=False)
        print(f"📁 Exported {len(df)} trades to {full_path}")

        # Export by universe
        if "universe" in df.columns:
            for universe in df["universe"].unique():
                univ_df = df[df["universe"] == universe]
                univ_path = export_path / f"{universe}.csv"
                univ_df.to_csv(univ_path, index=False)

        # Export by account size
        if "universe" in df.columns:
            df["account"] = df["universe"].str.split("_").str[0]
            for account in df["account"].unique():
                acc_df = df[df["account"] == account]
                acc_path = export_path / f"account_{account}.csv"
                acc_df.to_csv(acc_path, index=False)

        # Export by config
        if "universe" in df.columns:
            df["config"] = df["universe"].str.split("_").str[1]
            for config in df["config"].unique():
                cfg_df = df[df["config"] == config]
                cfg_path = export_path / f"config_{config}.csv"
                cfg_df.to_csv(cfg_path, index=False)

        print(f"✅ Export complete to {export_path}")

    def close(self):
        """Flush remaining buffer and close."""
        self.flush()
        print(
            f"📊 Shadow Logger session complete. Total trades: {len(self._existing_df) if self._existing_df is not None else 0}"
        )
