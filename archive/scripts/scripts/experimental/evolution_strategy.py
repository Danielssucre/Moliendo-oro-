import sys
import os
import pandas as pd
import numpy as np
import itertools
from pathlib import Path
from datetime import time, timedelta, datetime
from typing import List, Dict, Optional, Tuple

# Setup project path
sys.path.append(str(Path(__file__).parent.parent))

from src.trading_agent import TradingAgent
from src.utils.logger import logger
from src.utils.config import config
from src.analysis.backtester import Backtester, BacktestResult

class EvolutionBacktester(Backtester):
    """Backtester specialized for 100-trade blocks and external data."""
    def __init__(self, agent, spread_pips=1.5, commission_per_lot=6.0):
        super().__init__(agent)
        self.spread_pips = spread_pips
        self.commission_per_lot = commission_per_lot
        self.max_trades = 100 # EXIT CONDITION

    def run_evolution_block(self, pair: str, start_d, end_d, csv_dir, config_override=None):
        """Runs until 100 trades are reached."""
        logger.info(f"🧬 Iniciando bloque de 100 trades para {pair}...")
        
        # Data Loading
        df_5m_raw = pd.read_csv(os.path.join(csv_dir, "TIMEFRAME_5M.csv"), parse_dates=['time'], index_col='time')
        df_1h_raw = pd.read_csv(os.path.join(csv_dir, "TIMEFRAME_1H.csv"), parse_dates=['time'], index_col='time')
        
        def extract(raw_df, p):
            cols = [p, f"H-{p}", f"L-{p}", f"V-{p}"]
            df = raw_df[(raw_df.index.date >= start_d - timedelta(days=5)) & (raw_df.index.date <= end_d + timedelta(days=1))][cols].copy()
            df.columns = ['close', 'high', 'low', 'volume']
            df['open'] = df['close'].shift(1).fillna(df['close'])
            return df[['open', 'high', 'low', 'close', 'volume']]

        df_5m = extract(df_5m_raw, pair)
        df_1h = extract(df_1h_raw, pair)
        
        data_bundles = {
            '15min': df_5m.resample('15min').last().dropna(),
            '1h': df_1h,
            '4h': self._resample_data(df_1h, '4h'),
            '1d': self._resample_data(df_1h, '1d')
        }
        
        trades = []
        df_15m = data_bundles['15min']
        base_data = df_15m[(df_15m.index.date >= start_d) & (df_15m.index.date <= end_d)].copy()
        
        for check_ts in base_data.index:
            if len(trades) >= self.max_trades:
                logger.info(f"✅ Se han alcanzado los {self.max_trades} trades. Deteniendo bloque.")
                break
                
            current_window = {tf: df[df.index <= check_ts].tail(500) for tf, df in data_bundles.items()}
            
            # DECISION TREE BRAIN
            signal = self.agent.analyze_pair(
                pair, manual_data=current_window, 
                override_timestamp=check_ts,
                config_override=config_override
            )
            
            if signal:
                try:
                    raw_start_idx = df_5m.index.get_loc(check_ts)
                    trade_record, _ = self._simulate_trade_v2(df_5m, raw_start_idx, signal)
                    if trade_record:
                        exit_price = trade_record.get('exit_price', (signal.take_profit if trade_record['status'] == 'TP' else signal.stop_loss))
                        pl_gross, pips = self._calculate_realistic_pl(signal, exit_price, pair)
                        costs = (signal.position_size * self.commission_per_lot) + (self.spread_pips * 10 * self._get_pip_val(pair) * signal.position_size)
                        
                        trades.append({
                            'profit_loss': pl_gross - costs,
                            'status': trade_record['status'],
                            'timestamp': signal.timestamp,
                            'pips': pips
                        })
                except: continue
                
        return self._calculate_metrics(pair, trades)

    def _get_pip_val(self, pair):
        return 10.0 if "JPY" in pair else 0.0001
    
    def _calculate_realistic_pl(self, signal, exit_price, pair):
        pip_size = self._get_pip_val(pair)
        pips = (exit_price - signal.entry_price) / pip_size
        if signal.direction == "SELL": pips = -pips
        pl = pips * 10 * signal.position_size
        return pl, pips

    def _resample_data(self, df, tf):
        return df.resample(tf).last().dropna()

def start_evolution():
    kaggle_path = "/Users/danielsuarezsucre/.cache/kagglehub/datasets/anthonygocmen/multi-timeframe-fx-dataset-29-major-pairs/versions/2"
    
    # CORRECT WAY TO SWITCH PROFILE IN MEMORY
    config.trading["active_profile"] = "tree_evolution"
    config._apply_profile_overrides() 
    
    agent = TradingAgent(capital=100000)
    backtester = EvolutionBacktester(agent)
    
    # 90 day window for data extraction, but we stop at 100 trades
    h1_file = os.path.join(kaggle_path, "TIMEFRAME_1H.csv")
    df_dates = pd.read_csv(h1_file, usecols=['time'], parse_dates=['time'])
    unique_dates = sorted(df_dates['time'].dt.date.unique())
    start_d = unique_dates[-120] # More buffer to find 100 trades
    end_d = unique_dates[-1]

    # --- Pass 1: Initial Parameters ---
    logger.info("--- PASO 1: EVALUACIÓN BASE (Tree Evolution) ---")
    res = backtester.run_evolution_block("EURUSD", start_d, end_d, kaggle_path)
    
    print("\n" + "="*50)
    print(f"RESULTADOS BLOQUE INICIAL: {res.net_profit:.2f} P/L | {res.win_rate:.1%} WR")
    print("="*50)

    if res.net_profit > 0 and res.total_trades >= 10: # Min trades for valid optimization
        logger.info("🚀 Estrategia ganadora hallada. Iniciando Optimización Evolutiva...")
        
        # Optimization Logic
        optim_grid = {
            "adx_threshold": [15, 25],
            "min_threshold": [0.55, 0.65]
        }
        
        keys, values = zip(*optim_grid.items())
        param_combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
        
        best_score = res.net_profit
        best_params = {"adx_threshold": 20, "min_threshold": 0.60} # Initial

        for params in param_combinations:
            logger.info(f"Testing iteration: ADX={params['adx_threshold']} | Kalman={params['min_threshold']}")
            override = {
                "indicators": {"adx_threshold": params["adx_threshold"]},
                "probability": {"min_threshold": params["min_threshold"]}
            }
            
            res_opt = backtester.run_evolution_block("EURUSD", start_d, end_d, kaggle_path, config_override=override)
            
            if res_opt.net_profit > best_score:
                best_score = res_opt.net_profit
                best_params = params
                logger.info(f"🏆 Nueva mejor configuración: P/L ${best_score:.2f}")

        print("\n" + "="*50)
        print("OPTIMIZACIÓN EVOLUTIVA COMPLETADA")
        print(f"Mejor P/L: ${best_score:.2f}")
        print(f"Mejores Parámetros: {best_params}")
        print("="*50)
    else:
        logger.warning("❌ El bloque inicial no fue rentable o tuvo muy pocos trades para optimizar.")

if __name__ == "__main__":
    start_evolution()
