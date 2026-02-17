#!/usr/bin/env python3
"""
MT5 Data Source using SiliconMetaTrader5 (existing Docker container)
Uses the same MT5 instance that the trading bot uses
"""

from datetime import datetime, timedelta
import pandas as pd
import logging
from typing import Optional

try:
    from siliconmetatrader5 import MetaTrader5
    SILICON_MT5_AVAILABLE = True
except ImportError:
    SILICON_MT5_AVAILABLE = False
    print("⚠️  siliconmetatrader5 not installed. Install with: pip install siliconmetatrader5")


class MT5DataSource:
    """
    MetaTrader 5 data source using SiliconMetaTrader5 Docker
    
    Requires:
    - Docker container running: docker-siliconmt5
    - siliconmetatrader5 Python library installed
    - Port 8001 exposed and accessible
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8001):
        """
        Initialize MT5 data source
        
        Args:
            host: Docker container host (default: localhost)
            port: API port (default: 8001 for siliconmt5)
        """
        if not SILICON_MT5_AVAILABLE:
            raise ImportError("siliconmetatrader5 library not available")
            
        self.port = port
        self.mt5 = None
        self.connected = False
        self.logger = logging.getLogger(__name__)
        
    def connect(self) -> bool:
        """
        Establish connection to MT5 Docker container
        
        Returns:
            bool: True if connected successfully
        """
        try:
            self.mt5 = MetaTrader5(port=self.port)
            
            if not self.mt5.initialize():
                error = self.mt5.last_error()
                self.logger.error(f"❌ MT5 initialization failed: {error}")
                return False
            
            self.connected = True
            account_info = self.mt5.account_info()
            server = account_info.server if account_info else "Unknown"
            self.logger.info(f"✅ Connected to MT5 server: {server}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ MT5 connection error: {e}")
            return False
    
    def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        from_date: datetime,
        to_date: datetime
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data from MT5
        
        Args:
            symbol: Trading symbol (e.g., 'EURUSD', 'BTCUSD')
            timeframe: Timeframe string ('H1', 'M15', etc.)
            from_date: Start date
            to_date: End date
            
        Returns:
            DataFrame with columns: date, open, high, low, close, tick_volume, spread
        """
        if not self.connected:
            if not self.connect():
                self.logger.error("Cannot fetch data: Not connected to MT5")
                return pd.DataFrame()
        
        try:
            # Map timeframe string to MT5 constant
            timeframe_map = {
                'M1': self.mt5.TIMEFRAME_M1,
                'M5': self.mt5.TIMEFRAME_M5,
                'M15': self.mt5.TIMEFRAME_M15,
                'M30': self.mt5.TIMEFRAME_M30,
                'H1': self.mt5.TIMEFRAME_H1,
                'H4': self.mt5.TIMEFRAME_H4,
                'D1': self.mt5.TIMEFRAME_D1,
            }
            
            tf = timeframe_map.get(timeframe, self.mt5.TIMEFRAME_H1)
            
            # Ensure symbol is selected
            if not self.mt5.symbol_select(symbol, True):
                self.logger.warning(f"Symbol {symbol} selection failed")
                return pd.DataFrame()
            
            # Fetch data
            rates = self.mt5.copy_rates_range(symbol, tf, from_date, to_date)
            
            if rates is None or len(rates) == 0:
                self.logger.warning(f"No data returned for {symbol} {timeframe}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(rates)
            
            # Rename 'time' to 'date' for consistency
            if 'time' in df.columns:
                df['date'] = pd.to_datetime(df['time'], unit='s')
            
            self.logger.info(f"✅ Fetched {len(df)} bars for {symbol}")
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error fetching {symbol} data: {e}")
            return pd.DataFrame()
    
    def get_price_at_time(
        self,
        symbol: str,
        timestamp: datetime,
        timeframe: str = "H1"
    ) -> Optional[float]:
        """
        Get closing price at specific timestamp
        
        Args:
            symbol: Trading symbol
            timestamp: Exact timestamp to query
            timeframe: Timeframe to use
            
        Returns:
            Closing price or None if not found
        """
        # Fetch data around the timestamp
        start = timestamp - timedelta(hours=2)
        end = timestamp + timedelta(hours=2)
        
        df = self.get_historical_data(symbol, timeframe, start, end)
        
        if df.empty:
            return None
        
        # Find closest row to timestamp
        df['time_diff'] = abs((df['date'] - timestamp).dt.total_seconds())
        closest_idx = df['time_diff'].idxmin()
        
        return float(df.loc[closest_idx, 'close'])
    
    def get_atr(
        self,
        symbol: str,
        timestamp: datetime,
        period: int = 14,
        timeframe: str = "H1"
    ) -> Optional[float]:
        """
        Calculate ATR (Average True Range) at specific timestamp
        
        Args:
            symbol: Trading symbol
            timestamp: Timestamp to calculate ATR for
            period: ATR period (default: 14)
            timeframe: Timeframe to use
            
        Returns:
            ATR value or None if insufficient data
        """
        # Fetch enough data for ATR calculation
        lookback_days = max(7, period // 2)
        start = timestamp - timedelta(days=lookback_days)
        end = timestamp + timedelta(hours=1)
        
        df = self.get_historical_data(symbol, timeframe, start, end)
        
        if df.empty or len(df) < period:
            self.logger.warning(f"Insufficient data for ATR calculation: {len(df)} bars")
            return None
        
        try:
            # Filter data up to timestamp
            df_filtered = df[df['date'] <= timestamp].tail(period + 10)
            
            if len(df_filtered) < period:
                return None
            
            # Calculate True Range
            df_filtered = df_filtered.copy()
            df_filtered['high_low'] = df_filtered['high'] - df_filtered['low']
            df_filtered['high_close'] = abs(df_filtered['high'] - df_filtered['close'].shift())
            df_filtered['low_close'] = abs(df_filtered['low'] - df_filtered['close'].shift())
            
            df_filtered['true_range'] = df_filtered[['high_low', 'high_close', 'low_close']].max(axis=1)
            
            # Calculate ATR as rolling mean of True Range
            atr_series = df_filtered['true_range'].rolling(window=period).mean()
            atr_value = atr_series.iloc[-1]
            
            if pd.isna(atr_value):
                return None
                
            return float(atr_value)
            
        except Exception as e:
            self.logger.error(f"Error calculating ATR: {e}")
            return None
    
    def disconnect(self):
        """Cleanly disconnect from MT5"""
        if self.connected and self.mt5:
            try:
                self.mt5.shutdown()
                self.connected = False
                self.logger.info("Disconnected from MT5")
            except Exception as e:
                self.logger.error(f"Error disconnecting: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


def is_mt5_available() -> bool:
    """
    Check if MT5 data source is available
    
    Returns:
        bool: True if siliconmetatrader5 is installed and Docker container is reachable
    """
    if not SILICON_MT5_AVAILABLE:
        return False
    
    try:
        mt5 = MT5DataSource()
        connected = mt5.connect()
        mt5.disconnect()
        return connected
    except:
        return False


if __name__ == "__main__":
    # Test connection
    logging.basicConfig(level=logging.INFO)
    
    print("\n🔌 Testing MT5 Connection (SiliconMetaTrader5)...")
    
    if not SILICON_MT5_AVAILABLE:
        print("❌ siliconmetatrader5 not installed")
        print("   Install with: pip install siliconmetatrader5")
        exit(1)
    
    with MT5DataSource() as mt5:
        if mt5.connected:
            print("\n✅ MT5 Connection successful!")
            
            # Test data fetch
            print("\n📊 Fetching sample EURUSD data...")
            df = mt5.get_historical_data(
                symbol="EURUSD",
                timeframe="H1",
                from_date=datetime.now() - timedelta(days=5),
                to_date=datetime.now()
            )
            
            if not df.empty:
                print(f"\n✅ Fetched {len(df)} bars")
                print("\nSample data:")
                print(df[['date', 'open', 'high', 'low', 'close']].head())
            else:
                print("❌ No data returned")
        else:
            print("\n❌ MT5 Connection failed")
            print("   Make sure Docker container is running:")
            print("   docker ps | grep siliconmt5")
