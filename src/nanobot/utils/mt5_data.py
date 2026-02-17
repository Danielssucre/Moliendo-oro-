"""
Nanobot Utilities - Data Sources and Helpers.
"""
import os
import logging
from datetime import datetime, timedelta
import pandas as pd
from typing import Optional

try:
    from siliconmetatrader5 import MetaTrader5
    SILICON_MT5_AVAILABLE = True
except ImportError:
    SILICON_MT5_AVAILABLE = False

class MT5DataSource:
    """
    Institutional MT5 Data Source.
    Connects to SiliconMT5 Docker on port 8001.
    """
    def __init__(self, host: str = "127.0.0.1", port: int = 8001):
        self.port = port
        self.mt5 = None
        self.connected = False
        self.logger = logging.getLogger("Nanobot.MT5")
        
    def connect(self) -> bool:
        try:
            self.mt5 = MetaTrader5(port=self.port)
            if not self.mt5.initialize():
                return False
            self.connected = True
            return True
        except Exception as e:
            self.logger.error(f"MT5 Connection Error: {e}")
            return False
    
    def get_historical_data(self, symbol: str, timeframe: str, from_date: datetime, to_date: datetime) -> pd.DataFrame:
        if not self.connected and not self.connect():
            return pd.DataFrame()
        
        tf_map = {
            'M1': self.mt5.TIMEFRAME_M1, 'M5': self.mt5.TIMEFRAME_M5,
            'M15': self.mt5.TIMEFRAME_M15, 'M30': self.mt5.TIMEFRAME_M30,
            'H1': self.mt5.TIMEFRAME_H1, 'H4': self.mt5.TIMEFRAME_H4, 'D1': self.mt5.TIMEFRAME_D1,
        }
        tf = tf_map.get(timeframe, self.mt5.TIMEFRAME_H1)
        
        self.mt5.symbol_select(symbol, True)
        rates = self.mt5.copy_rates_range(symbol, tf, from_date, to_date)
        
        if rates is None or len(rates) == 0:
            return pd.DataFrame()
            
        df = pd.DataFrame(rates)
        if 'time' in df.columns:
            df['date'] = pd.to_datetime(df['time'], unit='s')
        return df

    def disconnect(self):
        if self.connected and self.mt5:
            self.mt5.shutdown()
            self.connected = False

    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
