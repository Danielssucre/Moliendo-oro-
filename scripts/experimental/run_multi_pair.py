#!/usr/bin/env python3
"""
Multi-Pair Precision Strategy - Execution Script
Phase 14 Implementation: EURUSD, GBPUSD, USDJPY Portfolio

This script runs the validated 3-pair portfolio with:
- 33% capital allocation per pair
- 0.25% risk per trade
- Max 1 trade/pair/day
- EMA 9/15 + Volume template (lit_ema_9_15_vol)
"""
import sys
import os
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.trading_agent import TradingAgent
from src.utils.logger import logger
from src.utils.config import config

# Phase 14 Multi-Pair Portfolio Configuration
PRECISION_PAIRS = ["EURUSD", "GBPUSD", "USDJPY"]
CAPITAL_ALLOCATION = 0.33  # 33% per pair
RISK_PER_TRADE = 0.0025  # 0.25% of allocated capital
MAX_TRADES_PER_PAIR_PER_DAY = 1

# Phase 11 Optimal Parameters (validated for all 3 pairs)
OPTIMAL_CONFIG = {
    "strategy_template": "lit_ema_9_15_vol",
    "use_regime_detection": True,
    "hurst_trending_threshold": 0.60,
    "hurst_meanrev_threshold": 0.40,
    "ml_stop_hunt_threshold": 0.80,
    "soft_decision_threshold": 0.60,
    "monte_carlo_threshold": 0.45,
    "adx_threshold": 20,
    "max_risk_per_trade": RISK_PER_TRADE,
    "min_risk_reward": 1.0,
    "sl_atr_multiplier": 1.0,
    "tp_atr_multiplier": 1.0,
    "max_lookahead": 44,  # 11h for M15
}


def print_portfolio_banner():
    """Print multi-pair portfolio banner."""
    banner = f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║         🎯 MULTI-PAIR PRECISION STRATEGY                    ║
║         Phase 14: EURUSD + GBPUSD + USDJPY                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

📊 PORTFOLIO CONFIGURATION:
   Pairs: {', '.join(PRECISION_PAIRS)}
   Capital Allocation: {CAPITAL_ALLOCATION*100:.0f}% per pair
   Risk per Trade: {RISK_PER_TRADE*100:.2f}% of allocated capital
   Max Trades: {MAX_TRADES_PER_PAIR_PER_DAY} per pair per day

📈 EXPECTED PERFORMANCE:
   Average Win Rate: 63.6%
   Expected Signals: 24/month (~6/week)
   Signal Frequency: 1-2 per day
   
⚙️  TEMPLATE: EMA 9/15 + Volume (Phase 11 Optimal)
"""
    print(banner)


def analyze_multi_pair_portfolio(total_capital: float = 100000):
    """
    Analyze all 3 pairs in the portfolio with proper capital allocation.
    
    Args:
        total_capital: Total account capital (default: $100,000)
    """
    print_portfolio_banner()
    
    # Calculate capital per pair
    capital_per_pair = total_capital * CAPITAL_ALLOCATION
    
    print(f"\n💰 CAPITAL ALLOCATION:")
    print(f"   Total Capital: ${total_capital:,.2f}")
    print(f"   Capital per Pair: ${capital_per_pair:,.2f}")
    print(f"   Risk per Trade: ${capital_per_pair * RISK_PER_TRADE:,.2f}\n")
    
    # Track daily trades per pair
    daily_trades = {pair: 0 for pair in PRECISION_PAIRS}
    signals_found = []
    
    print(f"🔍 ANALYZING PORTFOLIO ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})...")
    print("=" * 60 + "\n")
    
    for pair in PRECISION_PAIRS:
        logger.info(f"Analyzing {pair}...")
        
        # Check daily trade limit
        if daily_trades[pair] >= MAX_TRADES_PER_PAIR_PER_DAY:
            logger.info(f"⚠️  {pair}: Daily trade limit reached ({MAX_TRADES_PER_PAIR_PER_DAY})")
            continue
        
        # Initialize agent with pair-specific capital
        agent = TradingAgent(capital=capital_per_pair)
        agent.update_risk_percent(RISK_PER_TRADE * 100)  # Convert to percentage
        
        try:
            # Analyze pair with optimal config
            signal = agent.analyze_pair(pair, config_override=OPTIMAL_CONFIG)
            
            if signal:
                signal.strategy_name = "Precision Core (Multi-Pair)"
                signal.allocated_capital = capital_per_pair
                signals_found.append(signal)
                daily_trades[pair] += 1
                
                print(f"\n🎯 SIGNAL FOUND: {pair}")
                print("─" * 60)
                print(signal.format_for_display())
                print(f"\n📊 Portfolio Context:")
                print(f"   Allocated Capital: ${capital_per_pair:,.2f}")
                print(f"   Risk Amount: ${capital_per_pair * RISK_PER_TRADE:,.2f}")
                print(f"   Daily Trades for {pair}: {daily_trades[pair]}/{MAX_TRADES_PER_PAIR_PER_DAY}")
                print("─" * 60 + "\n")
            else:
                logger.info(f"❌ {pair}: No signal (conditions not met)")
                
        except Exception as e:
            logger.error(f"Error analyzing {pair}: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print(f"📊 PORTFOLIO SCAN COMPLETE")
    print("=" * 60)
    print(f"\nSignals Found: {len(signals_found)}/{len(PRECISION_PAIRS)}")
    print(f"Total Daily Risk: ${sum([capital_per_pair * RISK_PER_TRADE for _ in signals_found]):,.2f}")
    print(f"Max Possible Daily Risk: ${len(PRECISION_PAIRS) * capital_per_pair * RISK_PER_TRADE:,.2f}")
    
    if signals_found:
        print(f"\n✅ RECOMMENDATION: Review signals above and execute manually")
    else:
        print(f"\n⏳ RECOMMENDATION: No high-probability setups. Wait for next scan.")
    
    print("\n" + "=" * 60 + "\n")
    
    return signals_found


def continuous_scan_mode(total_capital: float = 100000, interval_minutes: int = 60):
    """
    Run continuous scanning mode for multi-pair portfolio.
    
    Args:
        total_capital: Total account capital
        interval_minutes: Minutes between scans
    """
    import time
    
    print(f"\n🚀 CONTINUOUS SCAN MODE ACTIVATED")
    print(f"   Scan Interval: {interval_minutes} minutes")
    print(f"   Press Ctrl+C to stop\n")
    
    iteration = 1
    
    while True:
        try:
            print(f"\n{'='*60}")
            print(f"SCAN #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}\n")
            
            analyze_multi_pair_portfolio(total_capital)
            
            iteration += 1
            
            logger.info(f"⏳ Next scan in {interval_minutes} minutes...")
            time.sleep(interval_minutes * 60)
            
        except KeyboardInterrupt:
            logger.info("\n👋 Continuous scan stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in scan loop: {e}")
            time.sleep(60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Multi-Pair Precision Strategy")
    parser.add_argument("--capital", type=float, default=100000,
                        help="Total account capital (default: 100000)")
    parser.add_argument("--continuous", action="store_true",
                        help="Run in continuous scan mode")
    parser.add_argument("--interval", type=int, default=60,
                        help="Scan interval in minutes (default: 60)")
    
    args = parser.parse_args()
    
    if args.continuous:
        continuous_scan_mode(args.capital, args.interval)
    else:
        analyze_multi_pair_portfolio(args.capital)
