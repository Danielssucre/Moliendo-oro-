import sys
import os
import json
import itertools
from pathlib import Path
import pandas as pd
from datetime import datetime
import time

# Add the parent directory to the path
sys.path.append(str(Path(__file__).parent.parent))

from src.trading_agent import TradingAgent
from src.analysis.backtester import Backtester
from src.utils.config import config
from src.api.api_manager import api_manager
from src.utils.logger import logger
import logging

def run_portfolio_optimization():
    # Target pairs (Colombian Portfolio)
    pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
    days = 30 # One month backtest for optimization
    
    # Optimization Grid
    grid = {
        "min_risk_reward_ratio": [1.5, 2.0, 3.0],
        "adx_threshold": [15, 20, 25],
        "stop_hunt_risk_threshold": [0.5, 0.65, 0.8]
    }
    
    agent = TradingAgent()
    backtester = Backtester(agent)
    
    # Pre-fetch data to avoid repeated API calls and handle rate limits upfront
    logger.info("📥 Descargando datos históricos para el portafolio...")
    for pair in pairs:
        for tf in ["15min", "1h", "4h", "1day"]:
            try:
                api_manager.get_forex_data(pair, tf, outputsize="full")
            except Exception as e:
                logger.error(f"Error pre-fetching {pair} {tf}: {e}")

    keys, values = zip(*grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    
    total_combos = len(combinations)
    logger.info(f"🚀 Iniciando Optimizador de Portafolio: {total_combos} combinaciones para {len(pairs)} pares")
    
    # Use Scalper M15 as base profile for high-frequency testing
    base_profile = config.trading["profiles"]["scalper_m15"]
    
    results = []
    
    # Silence logger for faster backtesting
    original_level = logger.logger.level
    logger.logger.setLevel(logging.WARNING)
    
    for i, combination in enumerate(combinations, 1):
        ctx_override = {
            "name": f"Opt-V2-{i}",
            "timeframes": base_profile["timeframes"],
            "risk_management": {
                "min_risk_reward_ratio": combination["min_risk_reward_ratio"]
            },
            "ml": {
                "stop_hunt_risk_threshold": combination["stop_hunt_risk_threshold"]
            },
            "indicators": {
                "adx_threshold": combination["adx_threshold"]
            }
        }
        
        # Aggregate stats for the whole portfolio
        total_profit = 0
        total_trades = 0
        total_win_rate = 0
        pairs_traded = 0
        total_pf = 0
        
        for pair in pairs:
            # step_skip=2 to speed up (every 30 mins for 15m entry)
            max_retries = 3
            res = None
            for retry in range(max_retries):
                try:
                    res = backtester.run(pair, days=days, config_override=ctx_override, step_skip=4)
                    break
                except Exception as e:
                    if retry == max_retries - 1:
                        logger.error(f"Failed {pair} after {max_retries} retries: {e}")
                        continue
                    logger.warning(f"Retry {retry+1}/{max_retries} for {pair} due to: {e}")
                    time.sleep(5)
            
            if res:
                total_profit += res.net_profit
                total_trades += res.total_trades
                if res.total_trades > 0:
                    total_win_rate += res.win_rate
                    total_pf += res.profit_factor
                    pairs_traded += 1
        
        avg_win_rate = total_win_rate / pairs_traded if pairs_traded > 0 else 0
        avg_pf = total_pf / pairs_traded if pairs_traded > 0 else 0
        
        # Score favors high profit factor and net profit, balanced by trade frequency
        score = total_profit * avg_pf * (avg_win_rate + 0.1)
        
        stats = {
            **combination,
            "net_profit": total_profit,
            "total_trades": total_trades,
            "win_rate": avg_win_rate,
            "profit_factor": avg_pf,
            "pairs_traded": pairs_traded,
            "score": score
        }
        
        results.append(stats)
        
        if i % 1 == 0 or i == total_combos:
            # Update best configuration
            best = max(results, key=lambda x: x["score"])
            
            # Temporarily restore logging to show progress
            logger.logger.setLevel(original_level)
            logger.info(f"Progreso: {i}/{total_combos} | Mejor Net Profit: ${best['net_profit']:.2f} | Score: {best['score']:.2f}")
            logger.info(f"   Mejor Parametros: RR={best['min_risk_reward_ratio']}, ADX={best['adx_threshold']}, ML={best['stop_hunt_risk_threshold']}")
            
            # Save incrementally
            with open("logs/portfolio_optimization_v2.json", "w") as f:
                json.dump(sorted(results, key=lambda x: x["score"], reverse=True), f, indent=4)
                
            logger.logger.setLevel(logging.WARNING)

    # Restore final logging level
    logger.logger.setLevel(original_level)

    # Display Top 5
    top_results = sorted(results, key=lambda x: x["score"], reverse=True)[:5]
    
    print("\n" + "="*80)
    print(f"🏆 MEJORES CONFIGURACIONES PARA PORTAFOLIO ROBUSTO")
    print("="*80)
    
    for idx, r in enumerate(top_results, 1):
        print(f"{idx}. Score: {r['score']:.2f} | Net Profit: ${r['net_profit']:.2f}")
        print(f"   WR: {r['win_rate']:.1%} | Avg PF: {r['profit_factor']:.2f} | Trades: {r['total_trades']}")
        print(f"   Parametros: RR={r['min_risk_reward_ratio']}, ADX={r['adx_threshold']}, ML_Threshold={r['stop_hunt_risk_threshold']}")
        print("-" * 60)

    # Save results to JSON
    output_path = Path("logs/portfolio_optimization_v2.json")
    with open(output_path, "w") as f:
        json.dump(top_results, f, indent=4)
        
    logger.info(f"✅ Resultados guardados en {output_path}")

if __name__ == "__main__":
    run_portfolio_optimization()
