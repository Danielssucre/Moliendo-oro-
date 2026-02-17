"""
Automated Strategy Optimizer - Hybrid Approach
Iterates through configurations until finding profitable setup for prop firms.

Goal:
- Win rate > 45%
- Profit Factor > 1.2
- Max Drawdown < 10%
- Suitable for manual trading (1 signal/day)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple
from datetime import time, datetime, timedelta
import pandas as pd
import numpy as np
from itertools import product

from src.trading_agent import TradingAgent
from scripts.backtest_external_data import ExternalDataBacktester
from src.utils.logger import logger


@dataclass
class OptimizerConfig:
    """Configuration for a single optimization run."""
    # Regime detection
    use_regime_detection: bool
    hurst_trending_threshold: float  # > this = trending
    hurst_meanrev_threshold: float   # < this = mean-reverting
    
    # Contrarian conditions (how many required to invert)
    contrarian_conditions_required: int
    rsi_extreme_low: float
    rsi_extreme_high: float
    volatility_spike_multiplier: float
    overreaction_std_threshold: float
    
    # Filter thresholds
    monte_carlo_threshold: float
    adx_threshold: float
    rsi_oversold: float
    rsi_overbought: float
    ml_stop_hunt_threshold: float
    
    # Risk management
    max_risk_per_trade: float
    min_risk_reward: float
    
    # Momentum Holding (Contratum)
    use_trailing_stop: bool
    trailing_stop_pips: float
    
    # Phase 9: Prop Firm Compliance
    max_lookahead: int = 40
    use_layered_assembly: bool = True
    soft_decision_threshold: float = 0.70
    
    # Phase 5: Calibration
    sl_atr_multiplier: float = 1.0
    tp_atr_multiplier: float = 1.5
    strategy_template: str = "basic_ema_cross"


@dataclass
class BacktestResult:
    """Result of a backtest run."""
    config: OptimizerConfig
    trades: int
    wins: int
    losses: int
    win_rate: float
    net_profit: float
    profit_factor: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    consecutive_wins: int
    consecutive_losses: int


class StrategyOptimizer:
    """Automated strategy optimizer with hybrid approach."""
    
    def __init__(self, sample_months: int = 3):
        """
        Initialize optimizer.
        
        Args:
            sample_months: Number of recent months to use for testing (faster)
        """
        self.data_path = Path.home() / ".cache/kagglehub/datasets/anthonygocmen/multi-timeframe-fx-dataset-29-major-pairs/versions/2"
        self.pairs = ["EURUSD", "GBPUSD", "USDJPY"]  # Phase 16: Test ADX template on 3-pair portfolio
        self.sample_months = sample_months
        self.best_result = None
        self.all_results = []
        
        # Target metrics for prop firm
        self.target_win_rate = 0.45
        self.target_profit_factor = 1.2
        self.target_max_dd_pct = 0.10
        
        # Phase 5: Nanobot Meta-Agent
        from src.nanobot.supervisor import NanobotSupervisor
        self.nanobot = NanobotSupervisor()  # 10%
        
        logger.info(f"🎯 Optimizer initialized with {sample_months}-month sample")
        logger.info(f"   Target: Win Rate > {self.target_win_rate*100:.0f}%, PF > {self.target_profit_factor}, DD < {self.target_max_dd_pct*100:.0f}%")
    
    def generate_configs(self) -> List[OptimizerConfig]:
        """Generate configurations for Phase 16: ADX Template Validation (Prop Firm Optimized)."""
        configs = []
        
        # Phase 16: Test ATR template (fallback)
        templates = ["lit_ema_9_15_atr"]
        
        # Lock Phase 11 optimal parameters
        hurst_trending = [0.60]
        hurst_meanrev = [0.40]
        mc_threshold = [0.45]
        sl_atr = [1.0]
        tp_atr = [1.0]
        soft_threshold = [0.60]
        adx_threshold = [20]
        ml_sh_threshold = [0.80]
        
        # Generate single config for AUDUSD
        for template, ht, hm, mc, sl_mult, tp_mult, adx, mlsh, soft in product(
            templates, hurst_trending, hurst_meanrev,
            mc_threshold, sl_atr, tp_atr, adx_threshold, ml_sh_threshold, soft_threshold
        ):
            configs.append(OptimizerConfig(
                use_regime_detection=True,
                hurst_trending_threshold=ht,
                hurst_meanrev_threshold=hm,
                contrarian_conditions_required=2,
                rsi_extreme_low=20,
                rsi_extreme_high=80,
                volatility_spike_multiplier=1.5,
                overreaction_std_threshold=2.0,
                monte_carlo_threshold=mc,
                adx_threshold=adx,
                rsi_oversold=20,
                rsi_overbought=80,
                ml_stop_hunt_threshold=mlsh,
                max_risk_per_trade=0.0025,  # 0.25%
                min_risk_reward=1.0,
                use_trailing_stop=False,
                trailing_stop_pips=0.0,
                sl_atr_multiplier=sl_mult,
                tp_atr_multiplier=tp_mult,
                max_lookahead=44,  # 11h for M15
                soft_decision_threshold=soft,
                strategy_template=template
            ))
        
        logger.info(f"📊 Generated {len(configs)} configurations to test")
        return configs
    
    def calculate_hurst_exponent(self, prices: pd.Series, lags: range = range(2, 100)) -> float:
        """
        Calculate Hurst exponent using R/S analysis.
        
        H > 0.5: Trending (persistent)
        H < 0.5: Mean-reverting (anti-persistent)
        H = 0.5: Random walk
        """
        tau = []
        lagvec = []
        
        for lag in lags:
            pp = np.subtract(prices.iloc[lag:].values, prices.iloc[:-lag].values)
            lagvec.append(lag)
            tau.append(np.sqrt(np.std(pp)))
        
        m = np.polyfit(np.log(lagvec), np.log(tau), 1)
        hurst = m[0] * 2.0
        
        return hurst
    
    def detect_regime(self, data: pd.DataFrame, config: OptimizerConfig) -> str:
        """
        Detect market regime using Hurst exponent.
        
        Returns: 'trending', 'mean_reverting', or 'uncertain'
        """
        if not config.use_regime_detection:
            return 'uncertain'
        
        prices = data['close'].tail(200)  # Use last 200 candles
        hurst = self.calculate_hurst_exponent(prices)
        
        if hurst > config.hurst_trending_threshold:
            return 'trending'
        elif hurst < config.hurst_meanrev_threshold:
            return 'mean_reverting'
        else:
            return 'uncertain'
    
    def check_contrarian_conditions(self, data: pd.DataFrame, config: OptimizerConfig) -> int:
        """
        Check how many contrarian conditions are met.
        
        Returns: Number of conditions met (0-4)
        """
        conditions_met = 0
        
        # 1. RSI extreme
        rsi = data['rsi'].iloc[-1] if 'rsi' in data.columns else 50
        if rsi < config.rsi_extreme_low or rsi > config.rsi_extreme_high:
            conditions_met += 1
        
        # 2. Volatility spike
        if 'atr' in data.columns:
            atr = data['atr'].iloc[-1]
            atr_ma = data['atr'].rolling(20).mean().iloc[-1]
            if atr > config.volatility_spike_multiplier * atr_ma:
                conditions_met += 1
        
        # 3. Over-reaction (return > X std deviations)
        returns = data['close'].pct_change()
        if len(returns) > 20:
            mean_ret = returns.rolling(20).mean().iloc[-1]
            std_ret = returns.rolling(20).std().iloc[-1]
            last_ret = returns.iloc[-1]
            if std_ret > 0:
                z_score = abs((last_ret - mean_ret) / std_ret)
                if z_score > config.overreaction_std_threshold:
                    conditions_met += 1
        
        # 4. Market stress (high ATR percentile or drawdown)
        if 'atr' in data.columns and len(data) > 100:
            atr_percentile = data['atr'].rank(pct=True).iloc[-1]
            if atr_percentile > 0.90:
                conditions_met += 1
        
        return conditions_met
    
    def should_invert_signal(self, data: pd.DataFrame, config: OptimizerConfig, regime: str) -> bool:
        """
        Determine if signal should be inverted based on regime and conditions.
        """
        # Check if inversion is allowed in this regime (Standard Hybrid logic)
        if regime == 'trending':
            return False  # Never invert in trending (follow the trend)
        if regime == 'uncertain':
            return False  # Too risky
        
        # Regime is mean_reverting: allow if contrarian conditions met
        
        # Check contrarian conditions
        conditions_met = self.check_contrarian_conditions(data, config)
        
        return conditions_met >= config.contrarian_conditions_required
    
    def run_backtest_with_config(self, config: OptimizerConfig) -> BacktestResult:
        """Run backtest with specific configuration."""
        agent = TradingAgent(capital=100000)
        
        # Apply config to agent
        agent.decision_tree.adx_threshold = config.adx_threshold
        agent.decision_tree.rsi_overbought = config.rsi_overbought
        agent.decision_tree.rsi_oversold = config.rsi_oversold
        agent.monte_carlo.min_probability = config.monte_carlo_threshold
        
        # Inject ML threshold into decision tree if possible
        if hasattr(agent.decision_tree, 'ml_model'):
            # This ensures Step 6 (ML Filter) uses the optimized threshold
            pass 
        
        backtester = ExternalDataBacktester(agent, spread_pips=1.2, commission_per_lot=6.0)
        
        all_trades = []
        for pair in self.pairs:
            trades = self._run_backtest_pair(backtester, pair, config)
            all_trades.extend(trades)
        
        return self._calculate_result(config, all_trades)
    
    def _run_backtest_pair(self, backtester, pair: str, config: OptimizerConfig) -> List[Dict]:
        """Run backtest for a single pair with hybrid logic."""
        # Normalize agent risk to the optimized level
        backtester.agent.update_risk_percent(config.max_risk_per_trade * 100)
        
        # Load data (sample only recent months)
        df_5m_raw = pd.read_csv(os.path.join(self.data_path, "TIMEFRAME_5M.csv"), 
                                parse_dates=['time'], index_col='time')
        df_15m_raw = pd.read_csv(os.path.join(self.data_path, "TIMEFRAME_15M.csv"), 
                                 parse_dates=['time'], index_col='time')
        df_1h_raw = pd.read_csv(os.path.join(self.data_path, "TIMEFRAME_1H.csv"), 
                                parse_dates=['time'], index_col='time')
        
        # Sample recent data only
        # We need a buffer for indicators, so we calculate two dates:
        # 1. The start date for ACTUAL trades (cutoff_date)
        # 2. The start date for DATA (data_start_date) to allow indicators to warm up
        cutoff_date = df_15m_raw.index.max() - timedelta(days=30 * self.sample_months)
        data_start_date = cutoff_date - timedelta(days=10) # 10 days buffer for indicators
        
        df_5m_raw = df_5m_raw[df_5m_raw.index >= data_start_date]
        df_15m_raw = df_15m_raw[df_15m_raw.index >= data_start_date]
        df_1h_raw = df_1h_raw[df_1h_raw.index >= data_start_date]
        
        def extract_pair_df(raw_df, p):
            cols = [p, f"H-{p}", f"L-{p}", f"V-{p}"]
            df = raw_df[cols].copy()
            df.columns = ['close', 'high', 'low', 'volume']
            df['open'] = df['close'].shift(1).fillna(df['close'])
            
            # Add RSI and ATR for regime/condition checks
            df['rsi'] = self._calculate_rsi(df['close'], 14)
            df['atr'] = self._calculate_atr(df, 14)
            
            return df[['open', 'high', 'low', 'close', 'volume', 'rsi', 'atr']]
        
        df_5m = extract_pair_df(df_5m_raw, pair)
        df_15m = extract_pair_df(df_15m_raw, pair)
        df_1h = extract_pair_df(df_1h_raw, pair)
        
        data_bundles = {
            '5min': df_5m,  # Add M5 for Dopamine Scalper
            '15min': df_15m,
            '1h': df_1h,
            '4h': backtester._resample_data(df_1h, '4h'),
            '1d': backtester._resample_data(df_1h, '1d')
        }
        
        trades = []
        df_15m['date_only'] = df_15m.index.date
        # Only run trades AFTER cutoff_date (keeping the 10-day buffer for indicators only)
        trades_data = df_15m[df_15m.index >= cutoff_date]
        days_to_check = trades_data['date_only'].unique()
        
        for day in days_to_check:
            day_data = trades_data[trades_data['date_only'] == day]
            window_data_points = day_data.between_time(time(19, 0), time(21, 0)).index
            
            trade_taken_today = False
            for check_ts in window_data_points:
                if trade_taken_today:
                    break
                
                current_window = {tf: df[df.index <= check_ts].tail(500) for tf, df in data_bundles.items()}
                
                # Detect regime
                regime = self.detect_regime(current_window['1h'], config)
                
                # Generate base signal
                # Pass ML threshold and ignore D1 in config_override
                local_cfg = {
                    'ml': {'stop_hunt_risk_threshold': config.ml_stop_hunt_threshold},
                    'signal': {'ignore_d1_alignment': True},
                    'probability': {
                        'min_monte_carlo_prob': config.monte_carlo_threshold,
                        'soft_decision_threshold': config.soft_decision_threshold
                    },
                    'risk_management': {
                        'atr_multiplier_sl': config.sl_atr_multiplier,
                        'atr_multiplier_tp': config.tp_atr_multiplier
                    },
                    'trading': {
                        'max_risk_per_trade': 0.0025 # Phase 9 Normalization
                    },
                    'max_lookahead': config.max_lookahead,
                    'strategy_template': config.strategy_template
                }
                if config.use_layered_assembly:
                    signal = backtester.agent.analyze_pair_layered(pair, manual_data=current_window, override_timestamp=check_ts, config_override=local_cfg)
                else:
                    signal = backtester.agent.analyze_scalp_pair(pair, manual_data=current_window, override_timestamp=check_ts, config_override=local_cfg)
                
                if signal:
                    # Phase 3 Log: Check if this was a 'Soft Pass'
                    is_soft_pass = signal.probability < 0.65
                    if is_soft_pass:
                        logger.debug(f"Signal is a 'Soft Pass' (Prob: {signal.probability:.1%})")
                    
                    # Hybrid decision: should we invert?
                    should_invert = self.should_invert_signal(current_window['15min'], config, regime)
                    
                    if should_invert:
                        signal.direction = "sell" if signal.direction == "buy" else "buy"
                        signal.take_profit, signal.stop_loss = signal.stop_loss, signal.take_profit
                    
                    try:
                        raw_start_idx = df_5m.index.get_loc(check_ts)
                        trade_record, _ = backtester._simulate_trade_v2(df_5m, raw_start_idx, signal, config_override=local_cfg)
                        
                        if trade_record:
                            exit_price = trade_record.get('exit_price', 
                                                          (signal.take_profit if trade_record['status'] == 'TP' else signal.stop_loss))
                            pl_gross, pips = backtester._calculate_realistic_pl(signal, exit_price, pair)
                            costs = (signal.position_size * backtester.commission_per_lot) + \
                                    (backtester.spread_pips * 10 * signal.position_size)
                            # Contratum logic: if inverted and using trailing stop
                            if should_invert and config.use_trailing_stop:
                                # If trade was profitable but not closed, we assume trailing stop helped 
                                # (This is a simplified assumption for the grid search)
                                if pips > 5.0: # If moved 5 pips in favor, reduce risk
                                    pass 
                            
                            trades.append({
                                'pair': pair,
                                'direction': signal.direction,
                                'status': trade_record['status'],
                                'pips': pips,
                                'profit_loss': pl_gross - costs,
                                'timestamp': signal.timestamp,
                                'regime': regime,
                                'inverted': should_invert
                            })
                            trade_taken_today = True
                    except (KeyError, ValueError):
                        continue
        
        return trades
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate ATR."""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        atr = true_range.rolling(period).mean()
        return atr
    
    def _calculate_result(self, config: OptimizerConfig, trades: List[Dict]) -> BacktestResult:
        """Calculate backtest metrics."""
        if not trades:
            return BacktestResult(
                config=config, trades=0, wins=0, losses=0, win_rate=0.0,
                net_profit=0.0, profit_factor=0.0, max_drawdown=0.0,
                max_drawdown_pct=0.0, sharpe_ratio=0.0, avg_win=0.0,
                avg_loss=0.0, largest_win=0.0, largest_loss=0.0,
                consecutive_wins=0, consecutive_losses=0
            )
        
        wins = [t for t in trades if t['status'] == 'TP']
        losses = [t for t in trades if t['status'] == 'SL']
        
        total_profit = sum(t['profit_loss'] for t in wins)
        total_loss = abs(sum(t['profit_loss'] for t in losses))
        net_profit = total_profit - total_loss
        
        profit_factor = total_profit / total_loss if total_loss > 0 else 0.0
        win_rate = len(wins) / len(trades) if trades else 0.0
        
        # Calculate drawdown
        cumulative_pl = []
        running_total = 100000  # Starting capital
        for t in sorted(trades, key=lambda x: x['timestamp']):
            running_total += t['profit_loss']
            cumulative_pl.append(running_total)
        
        peak = cumulative_pl[0]
        max_dd = 0
        for val in cumulative_pl:
            if val > peak:
                peak = val
            dd = peak - val
            if dd > max_dd:
                max_dd = dd
        
        max_dd_pct = max_dd / 100000 if cumulative_pl else 0.0
        
        # Sharpe ratio
        returns = [t['profit_loss'] for t in trades]
        if returns and len(returns) > 1:
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe = (mean_return / std_return) * np.sqrt(252) if std_return > 0 else 0.0
        else:
            sharpe = 0.0
        
        # Additional metrics
        avg_win = total_profit / len(wins) if wins else 0.0
        avg_loss = total_loss / len(losses) if losses else 0.0
        largest_win = max([t['profit_loss'] for t in wins]) if wins else 0.0
        largest_loss = min([t['profit_loss'] for t in losses]) if losses else 0.0
        
        # Consecutive wins/losses
        max_consec_wins = 0
        max_consec_losses = 0
        current_wins = 0
        current_losses = 0
        
        for t in sorted(trades, key=lambda x: x['timestamp']):
            if t['status'] == 'TP':
                current_wins += 1
                current_losses = 0
                max_consec_wins = max(max_consec_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consec_losses = max(max_consec_losses, current_losses)
        
        return BacktestResult(
            config=config,
            trades=len(trades),
            wins=len(wins),
            losses=len(losses),
            win_rate=win_rate,
            net_profit=net_profit,
            profit_factor=profit_factor,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            sharpe_ratio=sharpe,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            consecutive_wins=max_consec_wins,
            consecutive_losses=max_consec_losses
        )
    
    def meets_targets(self, result: BacktestResult) -> bool:
        """Check if result meets prop firm targets."""
        return (
            result.win_rate >= self.target_win_rate and
            result.profit_factor >= self.target_profit_factor and
            result.max_drawdown_pct <= self.target_max_dd_pct and
            result.trades >= 20  # Minimum sample size
        )
    
    def run_optimization(self, max_iterations: int = None):
        """
        Run optimization loop until finding profitable config.
        
        Args:
            max_iterations: Maximum iterations (None = unlimited)
        """
        configs = self.generate_configs()
        
        logger.info(f"\n{'='*100}")
        logger.info(f"🚀 STARTING AUTOMATED OPTIMIZATION")
        logger.info(f"   Configurations to test: {len(configs)}")
        logger.info(f"   Max iterations: {'Unlimited' if max_iterations is None else max_iterations}")
        logger.info(f"{'='*100}\n")
        
        iteration = 0
        for config in configs:
            if max_iterations and iteration >= max_iterations:
                logger.warning(f"⏸️  Reached max iterations ({max_iterations})")
                break
            
            iteration += 1
            logger.info(f"\n{'─'*100}")
            logger.info(f"🧪 ITERATION {iteration}/{len(configs)}")
            logger.info(f"   Template: {config.strategy_template}")
            logger.info(f"   Regime: Hurst {config.hurst_meanrev_threshold}-{config.hurst_trending_threshold}")
            logger.info(f"   Contrarian: {config.contrarian_conditions_required} conditions, RSI {config.rsi_extreme_low}-{config.rsi_extreme_high}")
            logger.info(f"   Filters: MC {config.monte_carlo_threshold*100:.0f}%, ADX {config.adx_threshold}")
            logger.info(f"{'─'*100}")
            
            result = self.run_backtest_with_config(config)
            self.all_results.append(result)
            
            # Print results
            logger.info(f"\n📊 RESULTS:")
            logger.info(f"   Trades: {result.trades} | Wins: {result.wins} | Losses: {result.losses}")
            logger.info(f"   Win Rate: {result.win_rate*100:.1f}% | PF: {result.profit_factor:.2f}")
            logger.info(f"   Net Profit: ${result.net_profit:,.2f}")
            logger.info(f"   Max DD: ${result.max_drawdown:,.2f} ({result.max_drawdown_pct*100:.1f}%)")
            logger.info(f"   Sharpe: {result.sharpe_ratio:.2f}")
            
            # Check if meets targets
            if self.meets_targets(result):
                logger.success(f"\n{'🎉'*50}")
                logger.success(f"✅ FOUND PROFITABLE CONFIGURATION!")
                logger.success(f"   Win Rate: {result.win_rate*100:.1f}% (target: {self.target_win_rate*100:.0f}%)")
                logger.success(f"   Profit Factor: {result.profit_factor:.2f} (target: {self.target_profit_factor})")
                logger.success(f"   Max DD: {result.max_drawdown_pct*100:.1f}% (target: <{self.target_max_dd_pct*100:.0f}%)")
                logger.success(f"{'🎉'*50}\n")
                
                self.best_result = result
                self._save_best_config()
                return result
            else:
                # Show what's missing
                missing = []
                if result.win_rate < self.target_win_rate:
                    missing.append(f"Win Rate {result.win_rate*100:.1f}% < {self.target_win_rate*100:.0f}%")
                if result.profit_factor < self.target_profit_factor:
                    missing.append(f"PF {result.profit_factor:.2f} < {self.target_profit_factor}")
                if result.max_drawdown_pct > self.target_max_dd_pct:
                    missing.append(f"DD {result.max_drawdown_pct*100:.1f}% > {self.target_max_dd_pct*100:.0f}%")
                
                logger.warning(f"   ❌ Missing: {', '.join(missing)}")
            
            # Update best if better than previous
            if self.best_result is None or result.profit_factor > self.best_result.profit_factor:
                self.best_result = result
                logger.info(f"   🏆 New best PF: {result.profit_factor:.2f}")

            # Phase 5: Periodic Nanobot Analysis
            if iteration % 20 == 0:
                logger.info("\n🤖 [Nanobot] Analyzing results trend...")
                results_dicts = [asdict(r) for r in self.all_results[-20:]]
                self.nanobot.analyze_results(results_dicts)
        
        # If we get here, no config met targets
        logger.warning(f"\n{'⚠️ '*50}")
        logger.warning(f"⚠️  NO CONFIGURATION MET ALL TARGETS")
        logger.warning(f"   Tested {len(self.all_results)} configurations")
        if self.best_result:
            logger.warning(f"   Best PF found: {self.best_result.profit_factor:.2f}")
            logger.warning(f"   Best Win Rate: {self.best_result.win_rate*100:.1f}%")
        logger.warning(f"{'⚠️ '*50}\n")
        
        self._save_best_config()
        return self.best_result
    
    def _save_best_config(self):
        """Save best configuration to file."""
        if not self.best_result:
            return
        
        output = {
            'config': asdict(self.best_result.config),
            'results': {
                'trades': self.best_result.trades,
                'win_rate': self.best_result.win_rate,
                'profit_factor': self.best_result.profit_factor,
                'net_profit': self.best_result.net_profit,
                'max_drawdown': self.best_result.max_drawdown,
                'max_drawdown_pct': self.best_result.max_drawdown_pct,
                'sharpe_ratio': self.best_result.sharpe_ratio,
                'avg_win': self.best_result.avg_win,
                'avg_loss': self.best_result.avg_loss
            }
        }
        
        output_file = Path(__file__).parent.parent / "logs" / "best_strategy_config.json"
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.success(f"💾 Best configuration saved to: {output_file}")


if __name__ == "__main__":
    # Run optimizer with 1-month sample (faster iteration)
    optimizer = StrategyOptimizer(sample_months=1)
    best = optimizer.run_optimization(max_iterations=None)  # Unlimited iterations
    
    if best and optimizer.meets_targets(best):
        logger.success("\n🎯 OPTIMIZATION SUCCESSFUL!")
        logger.success(f"   Ready for prop firm deployment")
    else:
        logger.warning("\n⚠️  OPTIMIZATION INCOMPLETE")
        logger.warning(f"   Consider expanding parameter grid or relaxing targets")
