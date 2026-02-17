import sys
import os
import pandas as pd
from pathlib import Path

# Setup project path
sys.path.append(str(Path(__file__).parent.parent))

from src.analysis.backtester import Backtester

class ExternalDataBacktester(Backtester):
    """Simplified backtester version for Kaggle data optimization."""
    def __init__(self, agent, spread_pips=1.2, commission_per_lot=6.0):
        super().__init__(agent)
        self.spread_pips = spread_pips
        self.commission_per_lot = commission_per_lot

    def _calculate_realistic_pl(self, signal, exit_price, pair):
        pip_size = 0.0001 if "JPY" not in pair.upper() else 0.01
        pips = (exit_price - signal.entry_price) / pip_size
        if signal.direction.upper() == "SELL": pips = -pips
        pl = pips * 10 * signal.position_size # $10/pip standard
        return pl, pips

    def _resample_data(self, df, tf):
        return df.resample(tf).last().dropna()
