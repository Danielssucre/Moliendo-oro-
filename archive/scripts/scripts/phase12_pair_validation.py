"""
Phase 12: Individual Pair Validation Script
Tests EMA 9/15 + Volume template on each pair separately to identify winners.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from dataclasses import dataclass
from typing import List, Dict
import pandas as pd

from src.trading_agent import TradingAgent
from scripts.backtest_external_data import ExternalDataBacktester
from src.utils.logger import logger

# Phase 11 Optimal Configuration
OPTIMAL_CONFIG = {
    "use_regime_detection": True,
    "hurst_trending_threshold": 0.60,
    "hurst_meanrev_threshold": 0.40,
    "contrarian_conditions_required": 2,
    "rsi_extreme_low": 20,
    "rsi_extreme_high": 80,
    "volatility_spike_multiplier": 1.5,
    "overreaction_std_threshold": 2.0,
    "monte_carlo_threshold": 0.45,
    "adx_threshold": 20,
    "rsi_oversold": 20,
    "rsi_overbought": 80,
    "ml_stop_hunt_threshold": 0.80,
    "max_risk_per_trade": 0.0025,  # 0.25%
    "min_risk_reward": 1.0,
    "use_trailing_stop": False,
    "trailing_stop_pips": 0.0,
    "sl_atr_multiplier": 1.0,
    "tp_atr_multiplier": 1.0,
    "max_lookahead": 44,  # 11h for M15
    "soft_decision_threshold": 0.60,
    "strategy_template": "lit_ema_9_15_vol"
}

PAIRS_TO_TEST = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
    "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY"
]

def test_single_pair(pair: str, optimizer) -> Dict:
    """Test a single pair with optimal config."""
    logger.info(f"\n{'='*80}")
    logger.info(f"🧪 TESTING {pair}")
    logger.info(f"{'='*80}")
    
    # Temporarily set optimizer to single pair
    original_pairs = optimizer.pairs
    optimizer.pairs = [pair]
    
    # Create config from optimal parameters
    from scripts.strategy_optimizer_loop import OptimizerConfig
    config = OptimizerConfig(**OPTIMAL_CONFIG)
    
    # Run backtest
    try:
        trades = optimizer.run_single_config(config)
    except Exception as e:
        logger.error(f"Error testing {pair}: {e}")
        optimizer.pairs = original_pairs
        return {
            "pair": pair,
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "max_dd_pct": 0.0,
            "status": "ERROR"
        }
    
    # Restore original pairs
    optimizer.pairs = original_pairs
    
    # Calculate metrics
    if not trades:
        logger.warning(f"❌ {pair}: No trades generated")
        return {
            "pair": pair,
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "max_dd_pct": 0.0,
            "status": "NO_SIGNALS"
        }
    
    wins = sum(1 for t in trades if t['profit_loss'] > 0)
    total_trades = len(trades)
    win_rate = wins / total_trades if total_trades > 0 else 0
    
    gross_profit = sum(t['profit_loss'] for t in trades if t['profit_loss'] > 0)
    gross_loss = abs(sum(t['profit_loss'] for t in trades if t['profit_loss'] < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    
    # Calculate drawdown
    equity = 100000
    peak = equity
    max_dd = 0
    for trade in trades:
        equity += trade['profit_loss']
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
    max_dd_pct = (max_dd / 100000) * 100
    
    result = {
        "pair": pair,
        "total_trades": total_trades,
        "win_rate": win_rate * 100,
        "profit_factor": profit_factor,
        "max_dd_pct": max_dd_pct,
        "status": "PASS" if win_rate >= 0.55 and profit_factor >= 1.2 else "FAIL"
    }
    
    logger.info(f"📊 {pair} Results:")
    logger.info(f"   Trades: {total_trades}")
    logger.info(f"   Win Rate: {win_rate*100:.1f}%")
    logger.info(f"   Profit Factor: {profit_factor:.2f}")
    logger.info(f"   Max DD: {max_dd_pct:.1f}%")
    logger.info(f"   Status: {result['status']}")
    
    return result

def main():
    """Run individual pair validation."""
    logger.info("🚀 Phase 12: Individual Pair Validation")
    logger.info(f"Testing {len(PAIRS_TO_TEST)} pairs with EMA 9/15 + Volume template")
    logger.info(f"Target: Win Rate ≥ 55%, Profit Factor ≥ 1.2\n")
    
    # Initialize optimizer
    from scripts.strategy_optimizer_loop import StrategyOptimizer
    optimizer = StrategyOptimizer(sample_months=3)
    
    results = []
    for pair in PAIRS_TO_TEST:
        result = test_single_pair(pair, optimizer)
        results.append(result)
    
    # Sort by win rate
    results.sort(key=lambda x: x['win_rate'], reverse=True)
    
    # Print summary
    logger.info(f"\n{'='*80}")
    logger.info("📊 FINAL RESULTS (Ranked by Win Rate)")
    logger.info(f"{'='*80}\n")
    
    winners = []
    for i, r in enumerate(results, 1):
        status_emoji = "✅" if r['status'] == "PASS" else "❌"
        logger.info(f"{i}. {status_emoji} {r['pair']}: {r['win_rate']:.1f}% WR | PF {r['profit_factor']:.2f} | DD {r['max_dd_pct']:.1f}% | {r['total_trades']} trades")
        if r['status'] == "PASS":
            winners.append(r['pair'])
    
    logger.info(f"\n{'='*80}")
    logger.info(f"🏆 WINNER PAIRS ({len(winners)}): {', '.join(winners)}")
    logger.info(f"   Expected Frequency: {len(winners) * 2.5:.0f}-{len(winners) * 3:.0f} signals/month")
    logger.info(f"{'='*80}\n")
    
    # Save results
    df = pd.DataFrame(results)
    output_file = Path(__file__).parent.parent / "logs" / "phase12_pair_validation.csv"
    df.to_csv(output_file, index=False)
    logger.info(f"💾 Results saved to: {output_file}")

if __name__ == "__main__":
    main()
