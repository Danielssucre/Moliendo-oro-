"""
STRATEGY TOURNAMENT: A/B/C Optimization
Runs 3 competing strategies on Kaggle dataset and selects the winner.
"""
import os
import sys
from pathlib import Path
from datetime import time
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Dict, List

sys.path.append(str(Path(__file__).parent.parent))
from src.utils.logger import logger
from src.trading_agent import TradingAgent
from scripts.backtest_external_data import ExternalDataBacktester

@dataclass
class StrategyResult:
    name: str
    description: str
    total_trades: int
    win_rate: float
    net_profit: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float = 0.0

class StrategyTournament:
    """Runs multiple strategy variants and selects the winner."""
    
    def __init__(self, kaggle_path: str):
        self.kaggle_path = kaggle_path
        self.pairs = ["EURUSD", "GBPUSD", "USDJPY"]
        self.results = []
    
    def run_strategy_a_deep_audit(self) -> StrategyResult:
        """
        STRATEGY A: Deep Audit
        - Relax RSI filter (30-70 → 20-80)
        - Lower D1 alignment requirement
        - Reduce Monte Carlo threshold (45% → 40%)
        """
        logger.info("🔍 STRATEGY A: Deep Audit - Relaxing Filters")
        
        agent = TradingAgent(capital=100000)
        # Inject relaxed config
        agent.decision_tree.rsi_oversold = 20
        agent.decision_tree.rsi_overbought = 80
        agent.decision_tree.min_probability = 0.40  # Lower MC threshold
        
        backtester = ExternalDataBacktester(agent, spread_pips=1.2, commission_per_lot=6.0)
        
        all_trades = []
        for pair in self.pairs:
            trades = self._run_backtest(backtester, pair)
            all_trades.extend(trades)
        
        return self._calculate_aggregate_result("Strategy A: Deep Audit", 
                                                 "Relaxed RSI + Lower MC Threshold", 
                                                 all_trades)
    
    def run_strategy_b_contrarian(self) -> StrategyResult:
        """
        STRATEGY B: Contrarian Inversion
        - Invert all signals (BUY → SELL, SELL → BUY)
        - Keep all filters intact
        """
        logger.info("🔄 STRATEGY B: Contrarian Inversion - Reversing Signals")
        
        agent = TradingAgent(capital=100000)
        backtester = ExternalDataBacktester(agent, spread_pips=1.2, commission_per_lot=6.0)
        
        all_trades = []
        for pair in self.pairs:
            trades = self._run_backtest(backtester, pair, invert_signals=True)
            all_trades.extend(trades)
        
        return self._calculate_aggregate_result("Strategy B: Contrarian", 
                                                 "Inverted Signals (BUY↔SELL)", 
                                                 all_trades)
    
    def run_strategy_c_simplified(self) -> StrategyResult:
        """
        STRATEGY C: Radical Simplification
        - Only H4 trend + RSI + ATR
        - No Kalman, No Monte Carlo, No ML Filter
        - Fixed RR 1:2
        """
        logger.info("⚡ STRATEGY C: Radical Simplification - Core Logic Only")
        
        agent = TradingAgent(capital=100000)
        # Disable complex filters
        agent.use_kalman = False
        agent.use_monte_carlo = False
        # ML filter will be bypassed via simple_mode=True in backtest
        
        backtester = ExternalDataBacktester(agent, spread_pips=1.2, commission_per_lot=6.0)
        
        all_trades = []
        for pair in self.pairs:
            trades = self._run_backtest(backtester, pair, simple_mode=True)
            all_trades.extend(trades)
        
        return self._calculate_aggregate_result("Strategy C: Simplified", 
                                                 "H4+RSI+ATR Only (No ML/MC)", 
                                                 all_trades)
    
    def _run_backtest(self, backtester, pair: str, invert_signals=False, simple_mode=False) -> List[Dict]:
        """Run backtest for a single pair with optional modifications."""
        logger.info(f"Testing {pair}...")
        
        # Load Kaggle data
        df_5m_raw = pd.read_csv(os.path.join(self.kaggle_path, "TIMEFRAME_5M.csv"), 
                                parse_dates=['time'], index_col='time')
        df_15m_raw = pd.read_csv(os.path.join(self.kaggle_path, "TIMEFRAME_15M.csv"), 
                                 parse_dates=['time'], index_col='time')
        df_1h_raw = pd.read_csv(os.path.join(self.kaggle_path, "TIMEFRAME_1H.csv"), 
                                parse_dates=['time'], index_col='time')
        
        def extract_pair_df(raw_df, p):
            cols = [p, f"H-{p}", f"L-{p}", f"V-{p}"]
            df = raw_df[cols].copy()
            df.columns = ['close', 'high', 'low', 'volume']
            df['open'] = df['close'].shift(1).fillna(df['close'])
            return df[['open', 'high', 'low', 'close', 'volume']]
        
        df_5m = extract_pair_df(df_5m_raw, pair)
        df_15m = extract_pair_df(df_15m_raw, pair)
        df_1h = extract_pair_df(df_1h_raw, pair)
        
        data_bundles = {
            '15min': df_15m,
            '1h': df_1h,
            '4h': backtester._resample_data(df_1h, '4h'),
            '1d': backtester._resample_data(df_1h, '1d')
        }
        
        trades = []
        df_15m['date_only'] = df_15m.index.date
        days_to_check = df_15m['date_only'].unique()
        
        for day in days_to_check:
            day_data = df_15m[df_15m['date_only'] == day]
            window_data_points = day_data.between_time(time(19, 0), time(21, 0)).index
            
            trade_taken_today = False
            for check_ts in window_data_points:
                if trade_taken_today: break
                
                current_window = {tf: df[df.index <= check_ts].tail(500) for tf, df in data_bundles.items()}
                
                if simple_mode:
                    # Simplified analysis (skip Dopamina sweep)
                    signal = backtester.agent.analyze_pair(pair, manual_data=current_window, override_timestamp=check_ts)
                else:
                    signal = backtester.agent.analyze_scalp_pair(pair, manual_data=current_window, override_timestamp=check_ts)
                
                if signal:
                    # INVERT SIGNAL IF CONTRARIAN MODE
                    if invert_signals:
                        signal.direction = "sell" if signal.direction == "buy" else "buy"
                        # Swap TP/SL
                        signal.take_profit, signal.stop_loss = signal.stop_loss, signal.take_profit
                    
                    try:
                        raw_start_idx = df_5m.index.get_loc(check_ts)
                        trade_record, _ = backtester._simulate_trade_v2(df_5m, raw_start_idx, signal)
                        
                        if trade_record:
                            exit_price = trade_record.get('exit_price', 
                                                          (signal.take_profit if trade_record['status'] == 'TP' else signal.stop_loss))
                            pl_gross, pips = backtester._calculate_realistic_pl(signal, exit_price, pair)
                            costs = (signal.position_size * backtester.commission_per_lot) + \
                                    (backtester.spread_pips * 10 * signal.position_size)
                            trades.append({
                                'pair': pair,
                                'direction': signal.direction,
                                'status': trade_record['status'],
                                'pips': pips,
                                'profit_loss': pl_gross - costs,
                                'timestamp': signal.timestamp
                            })
                            trade_taken_today = True
                    except (KeyError, ValueError):
                        continue
        
        return trades
    
    def _calculate_aggregate_result(self, name: str, description: str, trades: List[Dict]) -> StrategyResult:
        """Calculate aggregate metrics across all pairs."""
        if not trades:
            return StrategyResult(name, description, 0, 0.0, 0.0, 0.0, 0.0, 0.0)
        
        df = pd.DataFrame(trades)
        total_trades = len(df)
        wins = len(df[df['profit_loss'] > 0])
        win_rate = wins / total_trades if total_trades > 0 else 0
        
        net_profit = df['profit_loss'].sum()
        gross_wins = df[df['profit_loss'] > 0]['profit_loss'].sum()
        gross_losses = abs(df[df['profit_loss'] < 0]['profit_loss'].sum())
        profit_factor = gross_wins / gross_losses if gross_losses > 0 else 0
        
        # Calculate drawdown
        cumulative = df['profit_loss'].cumsum()
        running_max = cumulative.cummax()
        drawdown = running_max - cumulative
        max_drawdown = drawdown.max()
        
        # Sharpe Ratio (simplified)
        returns = df['profit_loss']
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
        
        return StrategyResult(
            name=name,
            description=description,
            total_trades=total_trades,
            win_rate=win_rate,
            net_profit=net_profit,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe
        )
    
    def run_tournament(self):
        """Execute all strategies and crown the winner."""
        print("\n" + "🏆"*50)
        print("STRATEGY TOURNAMENT: A vs B vs C")
        print("Dataset: Kaggle Multi-Timeframe (29 Pairs)")
        print("Pairs: EURUSD, GBPUSD, USDJPY")
        print("🏆"*50 + "\n")
        
        # Run all strategies
        result_a = self.run_strategy_a_deep_audit()
        result_b = self.run_strategy_b_contrarian()
        result_c = self.run_strategy_c_simplified()
        
        self.results = [result_a, result_b, result_c]
        
        # Display results
        print("\n" + "="*120)
        print(f"{'STRATEGY':<30} | {'TRADES':<7} | {'WIN %':<8} | {'NET PROFIT':<15} | {'PF':<6} | {'MAX DD':<12} | {'SHARPE'}")
        print("-"*120)
        
        for res in self.results:
            wr = res.win_rate * 100
            print(f"{res.name:<30} | {res.total_trades:<7} | {wr:>6.1f}% | ${res.net_profit:>13.2f} | {res.profit_factor:>4.2f} | ${res.max_drawdown:>10.2f} | {res.sharpe_ratio:>6.2f}")
        
        print("="*120)
        
        # Determine winner (by Net Profit)
        winner = max(self.results, key=lambda x: x.net_profit)
        
        print(f"\n🏆 WINNER: {winner.name}")
        print(f"   Description: {winner.description}")
        print(f"   Net Profit: ${winner.net_profit:,.2f}")
        print(f"   Win Rate: {winner.win_rate*100:.1f}%")
        print(f"   Profit Factor: {winner.profit_factor:.2f}")
        print(f"   Sharpe Ratio: {winner.sharpe_ratio:.2f}")
        print("\n" + "🏆"*50 + "\n")
        
        return winner

if __name__ == "__main__":
    kaggle_path = "/Users/danielsuarezsucre/.cache/kagglehub/datasets/anthonygocmen/multi-timeframe-fx-dataset-29-major-pairs/versions/2"
    
    if not os.path.exists(kaggle_path):
        logger.error("Kaggle dataset not found. Download it first.")
        sys.exit(1)
    
    tournament = StrategyTournament(kaggle_path)
    winner = tournament.run_tournament()
