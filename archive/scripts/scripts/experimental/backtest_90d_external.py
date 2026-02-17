import sys
import os
import pandas as pd
from pathlib import Path
from datetime import time, timedelta
from typing import List

# Setup project path
sys.path.append(str(Path(__file__).parent.parent))

from src.trading_agent import TradingAgent
from scripts.backtest_external_data import ExternalDataBacktester
from src.utils.logger import logger
from src.utils.config import config

def run_90d_institutional_backtest():
    """
    Runs a 90-day backtest using Kaggle data for the Golden Trio.
    Focus: Last 90 trading days available in the dataset.
    """
    # 1. Setup Agent & Backtester
    agent = TradingAgent(capital=100000)
    
    # Load Prop Hunter profile (Optimized for frequency/Challenge)
    config.active_profile = "prop_hunter"
    dopamina_cfg = config.get_profile_config("prop_hunter")
    agent.update_risk_percent(dopamina_cfg.get("risk_management", {}).get("risk_per_trade", 0.5))
    
    reality = ExternalDataBacktester(agent, spread_pips=1.2, commission_per_lot=6.0)
    
    # Kaggle Dataset Path
    kaggle_path = "/Users/danielsuarezsucre/.cache/kagglehub/datasets/anthonygocmen/multi-timeframe-fx-dataset-29-major-pairs/versions/2"
    
    if not os.path.exists(kaggle_path):
        logger.error(f"Dataset not found at {kaggle_path}")
        return

    print("\n" + "🚀"*45)
    print("INICIANDO BACKTEST DE 90 DÍAS (GOLDEN TRIO)")
    print("ESTRATEGIA: DOPAMINA (SCALPER M15) - OPTIMIZADA")
    print("DATA: KAGGLE INSTITUTIONAL (M5/M15/H1)")
    print("🚀"*45 + "\n")

    pairs_to_test = ["EURUSD", "GBPUSD", "USDJPY"]
    
    # 2. Extract Date Range (90 Trading Days)
    # We use 1H data to find the last 90 unique dates
    h1_file = os.path.join(kaggle_path, "TIMEFRAME_1H.csv")
    df_h1_dates = pd.read_csv(h1_file, usecols=['time'], parse_dates=['time'])
    df_h1_dates['date'] = df_h1_dates['time'].dt.date
    unique_dates = sorted(df_h1_dates['date'].unique())
    
    if len(unique_dates) < 90:
        logger.warning(f"Dataset only has {len(unique_dates)} trading days. Running full range.")
        start_date = unique_dates[0]
    else:
        start_date = unique_dates[-90]
    
    end_date = unique_dates[-1]
    logger.info(f"📊 Rango de Análisis: {start_date} al {end_date} ({len(unique_dates[-90:])} días)")

    # 3. Custom Run Method to filter by 90-day window
    def get_pip_value(pair: str) -> float:
        return 10.0 if "JPY" in pair.upper() else 0.0001

    def run_filtered_kaggle_backtest(backtester, csv_dir, pair, start_d, end_d):
        """Modified version of run_kaggle_backtest that filters dates."""
        df_5m_raw = pd.read_csv(os.path.join(csv_dir, "TIMEFRAME_5M.csv"), parse_dates=['time'], index_col='time')
        df_15m_raw = pd.read_csv(os.path.join(csv_dir, "TIMEFRAME_15M.csv"), parse_dates=['time'], index_col='time')
        df_1h_raw = pd.read_csv(os.path.join(csv_dir, "TIMEFRAME_1H.csv"), parse_dates=['time'], index_col='time')
        
        # Filter raw data for performance and precision
        # Add a 500 bar padding for technical indicators initialization
        padding_start = pd.Timestamp(start_d) - timedelta(days=5)
        
        def extract_and_filter(raw_df, p, s, e):
            cols = [p, f"H-{p}", f"L-{p}", f"V-{p}"]
            df = raw_df[(raw_df.index >= padding_start) & (raw_df.index <= pd.Timestamp(e) + timedelta(days=1))][cols].copy()
            df.columns = ['close', 'high', 'low', 'volume']
            df['open'] = df['close'].shift(1).fillna(df['close'])
            return df[['open', 'high', 'low', 'close', 'volume']]

        df_5m = extract_and_filter(df_5m_raw, pair, start_d, end_d)
        df_15m = extract_and_filter(df_15m_raw, pair, start_d, end_d)
        df_1h = extract_and_filter(df_1h_raw, pair, start_d, end_d)
        
        # Resample
        data_bundles = {
            '15min': df_15m,
            '1h': df_1h,
            '4h': backtester._resample_data(df_1h, '4h'),
            '1d': backtester._resample_data(df_1h, '1d')
        }
        
        trades = []
        # Filter base_data precisely for the 90-day window
        base_data = df_15m[(df_15m.index.date >= start_d) & (df_15m.index.date <= end_d)].copy()
        base_data['date_only'] = base_data.index.date
        days_to_check = base_data['date_only'].unique()
        
        for day in days_to_check:
            day_data = base_data[base_data['date_only'] == day]
            # Asia session window (UTC)
            window_data_points = day_data.between_time(time(19,0), time(21,0)).index
            
            trade_taken_today = False
            for check_ts in window_data_points:
                if trade_taken_today: break
                
                # Bundle current data (history up to check_ts)
                current_window = {tf: df[df.index <= check_ts].tail(500) for tf, df in data_bundles.items()}
                
                # Use analyze_pair with Dopamina config override
                signal = backtester.agent.analyze_pair(pair, manual_data=current_window, 
                                                    override_timestamp=check_ts,
                                                    config_override=dopamina_cfg)
                
                if signal:
                    try:
                        raw_start_idx = df_5m.index.get_loc(check_ts)
                        # v2 simulation uses fine-grained 5m data
                        trade_record, _ = backtester._simulate_trade_v2(df_5m, raw_start_idx, signal)
                        
                        if trade_record:
                            exit_price = trade_record.get('exit_price', (signal.take_profit if trade_record['status'] == 'TP' else signal.stop_loss))
                            pl_gross, pips = backtester._calculate_realistic_pl(signal, exit_price, pair)
                            costs = (signal.position_size * backtester.commission_per_lot) + (backtester.spread_pips * 10 * get_pip_value(pair) * signal.position_size)
                            
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
                        
        return backtester._calculate_metrics(pair, trades)

    # 4. Execute for all pairs
    results = []
    for pair in pairs_to_test:
        logger.info(f"⏳ Analizando {pair}...")
        res = run_filtered_kaggle_backtest(reality, kaggle_path, pair, start_date, end_date)
        results.append(res)
    
    # 5. Final Report
    print("\n" + "🏁"*45)
    print(f"{'PAR':<10} | {'TRADES':<6} | {'WIN %':<8} | {'P&L ($)':<14} | {'PF':<6} | {'MAX DD'}")
    print("-" * 88)
    
    total_net = 0
    total_trades = 0
    
    for res in results:
        wr = res.win_rate * 100
        print(f"{res.pair:<10} | {res.total_trades:<6} | {wr:>6.1f}% | ${res.net_profit:>12.2f} | {res.profit_factor:>4.2f} | ${res.max_drawdown:>8.2f}")
        total_net += res.net_profit
        total_trades += res.total_trades
    
    print("-" * 88)
    print(f"{'TOTAL':<10} | {total_trades:<6} | {'-':<8} | ${total_net:>12.2f} | {'-':<6} | {'-'}")
    print("="*88 + "\n")

if __name__ == "__main__":
    run_90d_institutional_backtest()
