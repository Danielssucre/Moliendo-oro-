import sys
import os
import json
import pandas as pd
from pathlib import Path
from datetime import timedelta

sys.path.append(str(Path(__file__).parent.parent))

from src.trading_agent import TradingAgent
from src.analysis.backtester import Backtester
from src.ml.stop_hunt_model import StopHuntModel
from src.utils.logger import logger

def collect_training_data():
    pairs = ["AUDUSD", "GBPUSD", "USDCAD"] # Golden Trio only
    days = 40 # 40 days is a good balance
    
    agent = TradingAgent()
    backtester = Backtester(agent)
    ml_handler = StopHuntModel()
    
    dataset = []
    output_path = Path(__file__).parent.parent / "data" / "stop_hunt_dataset.csv"
    os.makedirs(output_path.parent, exist_ok=True)
    
    try:
        for pair in pairs:
            logger.info(f"📊 Recolectando datos para {pair}...")
            tfs = agent.timeframes
            data_bundles = backtester._get_historical_bundles(pair, days, timeframes_dict=tfs)
            base_tf = tfs['short']
            base_data = data_bundles[base_tf]
            
            for i in range(300, len(base_data) - 48):
                current_timestamp = base_data.index[i]
                window_data = {tf: df[df.index <= current_timestamp].tail(500) for tf, df in data_bundles.items()}
                
                # Analyze without logging progress to terminal to avoid noise
                signal = agent.analyze_pair(pair, manual_data=window_data, override_timestamp=current_timestamp)
                
                if signal:
                    # Ground Truth
                    found_sl = False
                    found_tp_after_sl = False
                    for j in range(i + 1, min(i + 96, len(base_data))): # 24-48h
                        low = base_data.iloc[j]['low']
                        high = base_data.iloc[j]['high']
                        
                        if signal.direction == "BUY":
                            if low <= signal.stop_loss and not found_sl:
                                found_sl = True
                            if high >= signal.take_profit:
                                if found_sl: found_tp_after_sl = True
                                break
                        else: # SELL
                            if high >= signal.stop_loss and not found_sl:
                                found_sl = True
                            if low <= signal.take_profit:
                                if found_sl: found_tp_after_sl = True
                                break
                    
                    indicators = agent.probability_filter.analyzed_indicators
                    features = ml_handler.extract_features(window_data[base_tf], signal.entry_price, indicators)
                    
                    if features:
                        features['label'] = 1 if found_tp_after_sl else 0
                        features['pair'] = pair
                        dataset.append(features)
                        
                        if len(dataset) % 10 == 0:
                            logger.info(f"💾 Autosave! Samples: {len(dataset)} | Hunts: {sum(d['label'] for d in dataset)}")
                            pd.DataFrame(dataset).to_csv(output_path, index=False)

    except KeyboardInterrupt:
        logger.warning("Terminado por usuario. Guardando lo recolectado...")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        if dataset:
            pd.DataFrame(dataset).to_csv(output_path, index=False)
            logger.info(f"🏆 Dataset final guardado con {len(dataset)} filas en {output_path}")

if __name__ == "__main__":
    collect_training_data()
