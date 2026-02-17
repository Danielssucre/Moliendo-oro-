import pandas as pd
import numpy as np
import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

sys.path.append(str(Path(__file__).parent.parent))

from src.trading_agent import TradingAgent
from src.analysis.backtester import Backtester
from src.utils.logger import logger
from src.utils.config import config

class FTMOSimulator:
    def __init__(self, initial_capital=10000.0):
        self.capital = initial_capital
        self.balance = initial_capital
        self.equity = initial_capital
        self.daily_start_balance = initial_capital
        self.max_balance = initial_capital
        self.max_daily_drawdown = 0.05 * initial_capital # FTMO 5%
        self.max_total_drawdown = 0.10 * initial_capital # FTMO 10%
        self.profit_target = 0.10 * initial_capital # FTMO 10%
        
        # Realistic costs
        self.costs = {
            "EURUSD": {"spread": 0.8, "slippage": 0.3}, # in pips
            "GBPUSD": {"spread": 1.2, "slippage": 0.5},
            "AUDUSD": {"spread": 1.0, "slippage": 0.4},
            "USDCAD": {"spread": 1.5, "slippage": 0.5},
            "USDJPY": {"spread": 0.8, "slippage": 0.3}
        }
        
        self.trades = []
        self.daily_pnl = {}
        
    def run_simulation(self, pairs: List[str], days: int = 40):
        logger.info(f"🏆 Iniciando Simulación FTMO Challenge - Capital: ${self.capital:,.2f}")
        logger.info(f"📋 Reglas: Target +10%, Max Daily -5%, Max Total -10%")
        
        agent = TradingAgent(capital=self.capital)
        backtester = Backtester(agent)
        
        # Profiles to simulate together
        profiles = ["scalper_m15", "sniper_golden"]
        
        # 1. Fetch all data first to avoid redundant API calls
        all_data = {}
        for pair in pairs:
            logger.info(f"📥 Descargando datos para {pair}...")
            # Use a conservative set of timeframes that covers both profiles
            tfs = {"15min": "15min", "1h": "1h", "4h": "4h", "D1": "D1"}
            all_data[pair] = backtester._get_historical_bundles(pair, days, tfs)
            
        # 2. Timeline Simulation
        # We simulate day by day to track daily drawdown
        start_date = datetime.now() - timedelta(days=days)
        current_date = start_date
        
        history = []
        
        while current_date < datetime.now():
            day_str = current_date.strftime("%Y-%m-%d")
            self.daily_start_balance = self.balance
            day_trades_count = 0
            
            for pair in pairs:
                for profile in profiles:
                    # Apply profile config
                    profile_config = config.get_trading_config(f"profiles.{profile}")
                    tfs = profile_config['timeframes']
                    
                    # Run backtest for this day specifically
                    # (Optimization: Instead of running the whole backtester, we just check signals for this day)
                    # For simplicity in this script, we'll use the backtester's run logic narrowed
                    
                    try:
                        # Extract data for this pair and profile
                        # base_tf = tfs['short']
                        # ... logic to run only for current_date ...
                        # For now, let's use a simpler approach: run backtest Once per pair/profile and merge
                        pass
                    except:
                        continue
            
            current_date += timedelta(days=1)

        # SIMPLIFIED APPROACH:
        # 1. Run full backtests for each pair/profile
        # 2. Merge all trades into a single timeline
        # 3. Process timeline step by step to check FTMO violations
        
        all_raw_trades = []
        for pair in pairs:
            for profile in profiles:
                logger.info(f"🔎 Analizando {pair} con perfil {profile}...")
                profile_config = config.get_trading_config(f"profiles.{profile}")
                # FTMO Safety: Reduce risk per trade to 0.75% (2.0% is too aggressive for daily DD)
                risk_target = 0.75
                
                # Update agent strictly
                agent.update_capital(self.balance)
                agent.update_risk_percent(risk_target)
                
                # Also inject into config_override for decision tree consistency
                if "risk_management" not in profile_config:
                    profile_config["risk_management"] = {}
                profile_config["risk_management"]["max_risk_per_trade_percent"] = risk_target
                
                res = backtester.run(pair, days=days, config_override=profile_config)
                for t in res.trades:
                    t['profile'] = profile
                    all_raw_trades.append(t)
                    
        # Sort trades by timestamp
        all_raw_trades.sort(key=lambda x: x['timestamp'])
        
        # 3. Process Trades with Costs and FTMO Rules
        logger.info(f"📊 Procesando {len(all_raw_trades)} operaciones totales...")
        
        current_day = ""
        daily_loss = 0
        failed = False
        failure_reason = ""
        
        for t in all_raw_trades:
            trade_day = t['timestamp'].split(" ")[0]
            if trade_day != current_day:
                current_day = trade_day
                self.daily_start_balance = self.balance
                daily_loss = 0
                
            # Apply costs
            pair_costs = self.costs.get(t['pair'], {"spread": 1.5, "slippage": 0.5})
            total_cost_pips = pair_costs['spread'] + (pair_costs['slippage'] * 2) # Entry + Exit slippage
            
            # Recalculate P&L with costs
            # $10 per pip per lot is the approximation used in backtester
            cost_amount = total_cost_pips * 10 * (t['profit_loss'] / (t['pips'] * 10)) if t['pips'] != 0 else 0
            # Wait, easier: t['profit_loss'] is based on pips. 
            # If t['pips'] was 20, and cost is 2, adjusted pips is 18.
            adjusted_pips = t['pips'] - total_cost_pips
            lot_size = t['profit_loss'] / (t['pips'] * 10) if t['pips'] != 0 else 0
            adjusted_pnl = adjusted_pips * 10 * lot_size
            
            self.balance += adjusted_pnl
            self.equity = self.balance
            
            # Track Daily Drawdown
            if self.balance < self.daily_start_balance:
                daily_loss = self.daily_start_balance - self.balance
                if daily_loss > self.max_daily_drawdown:
                    failed = True
                    failure_reason = f"Daily Drawdown Limit Exceeded: -${daily_loss:,.2f} on {trade_day}"
                    break
                    
            # Track Total Drawdown
            if self.balance < self.capital - self.max_total_drawdown:
                failed = True
                failure_reason = f"Total Drawdown Limit Exceeded: ${self.balance:,.2f}"
                break
                
            history.append({
                "time": t['timestamp'],
                "pair": t['pair'],
                "profile": t['profile'],
                "pnl": adjusted_pnl,
                "balance": self.balance
            })

            # Peak tracking for total DD
            if self.balance > self.max_balance:
                self.max_balance = self.balance

        # 4. Final Report
        self._print_report(failed, failure_reason)

    def _print_report(self, failed, reason):
        print("\n" + "="*50)
        print("🚩 REPORTE DE SIMULACIÓN FTMO CHALLENGE")
        print("="*50)
        print(f"Estado Final: {'❌ FALLIDO' if failed else '✅ PASADO' if self.balance >= self.capital + self.profit_target else '⏳ EN CURSO'}")
        if failed:
            print(f"Razón: {reason}")
        print(f"Balance Final: ${self.balance:,.2f}")
        print(f"Retorno Neto: {((self.balance/self.capital)-1)*100:.2f}%")
        print(f"Max Balance: ${self.max_balance:,.2f}")
        print(f"Target Profit: +${self.profit_target:,.2f}")
        print("-" * 50)
        
        if not failed and self.balance >= self.capital + self.profit_target:
            print("🚀 ¡FELICIDADES! La estrategia pasó el challenge.")
        elif not failed:
            print("📈 La estrategia es rentable pero no alcanzó el target en el tiempo simualdo.")
        print("="*50 + "\n")

if __name__ == "__main__":
    sim = FTMOSimulator(initial_capital=10000.0)
    # Testing with major pairs for 30 days for faster results
    sim.run_simulation(["GBPUSD", "AUDUSD", "USDCAD"], days=30)
