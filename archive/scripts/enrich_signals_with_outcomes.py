#!/usr/bin/env python3
"""
Enrich Logseq signals with simulated outcomes using yfinance (macOS compatible).

This script reads Logseq markdown files, identifies signals that passed HIVE,
queries yfinance for historical prices, simulates TP/SL outcomes, and updates
the markdown with simulated PnL data.

Author: Nanobot Team
Version: 2.0.0 - macOS compatible
"""

import os
import sys
import re
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

# Configuration
LOGSEQ_DIR = Path.home() / "Desktop" / "Nanobot-Logseq"
JOURNALS_DIR = LOGSEQ_DIR / "journals"
PAGES_DIR = LOGSEQ_DIR / "pages"

# Simulation parameters
SIMULATION_WINDOW_HOURS = 24
SL_MULT = 1.5
TP_MULT = 2.0
ATR_PERIOD = 14

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)

# Import yfinance and pandas
try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
    import pytz
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logging.error("❌ yfinance not available. Install with: pip install yfinance pandas")
    sys.exit(1)

# Import MT5 data source (optional)
try:
    from mt5_data_source import MT5DataSource, is_mt5_available
    MT5_AVAILABLE = is_mt5_available()
    if MT5_AVAILABLE:
        logging.info("✅ Using MT5 as primary data source (Docker)")
    else:
        logging.info("⚠️  MT5 not available, using yfinance as fallback")
except ImportError:
    MT5_AVAILABLE = False
    logging.info("⚠️  MT5 module not found, using yfinance")

# Symbol mapping: MT5 -> yfinance
SYMBOL_MAP = {
    'BTCUSD': 'BTC-USD',
    'EURUSD': 'EURUSD=X',
    'GBPUSD': 'GBPUSD=X',
    'USDJPY': 'USDJPY=X',
    'AUDUSD': 'AUDUSD=X',
    'USDCAD': 'USDCAD=X',
    'NZDUSD': 'NZDUSD=X',
    'USDCHF': 'USDCHF=X',
    'GBPJPY': 'GBPJPY=X',
    'EURNZD': 'EURNZD=X',
    'GBPNZD': 'GBPNZD=X',
}


class OutcomeEnricher:
    """Enrich Logseq signals with simulated outcomes using MT5 or yfinance."""
    
    def __init__(self, logseq_dir: str, prefer_mt5: bool = True):
        self.logseq_dir = Path(logseq_dir)
        self.journals_dir = self.logseq_dir / "journals"
        self.pages_dir = self.logseq_dir / "pages"
        
        # Determine data source
        self.data_source = 'yfinance'  # Default
        self.mt5 = None
        
        if prefer_mt5 and MT5_AVAILABLE:
            try:
                self.mt5 = MT5DataSource()
                if self.mt5.connect():
                    self.data_source = 'mt5'
                    logging.info(f"✅ Data source: MT5 (real broker data with spreads)")
                else:
                    logging.warning("MT5 connection failed, falling back to yfinance")
                    self.data_source = 'yfinance'
            except Exception as e:
                logging.warning(f"MT5 initialization failed: {e}, using yfinance")
                self.data_source = 'yfinance'
        else:
            logging.info(f"✅ Data source: yfinance (macOS compatible)")
        
        # Cache for ticker data
        self.ticker_cache = {}
        
        # Statistics
        self.stats = {
            'signals_enriched': 0,
            'data_unavailable': 0,
            'errors': 0
        }

    
    def convert_symbol(self, mt5_symbol: str) -> Optional[str]:
        """Convert MT5 symbol to yfinance ticker."""
        return SYMBOL_MAP.get(mt5_symbol)
    
    def get_ticker_data(self, symbol: str, start_time: datetime, end_time: datetime) -> Optional[pd.DataFrame]:
        """Get historical data from MT5 or yfinance (with fallback)."""
        try:
            # Try MT5 first if available
            if self.data_source == 'mt5' and self.mt5:
                df = self.mt5.get_historical_data(
                    symbol=symbol,
                    timeframe="H1",
                    from_date=start_time - timedelta(days=2),
                    to_date=end_time + timedelta(hours=1)
                )
                
                if not df.empty:
                    # Standardize MT5 dataframe
                    df = df.rename(columns={'date': 'time'})
                    df['time'] = pd.to_datetime(df['time'])
                    return df
                else:
                    logging.warning(f"No MT5 data for {symbol}, trying yfinance fallback...")
            
            # Fallback to yfinance (or primary if MT5 not available)
            yf_symbol = self.convert_symbol(symbol)
            if not yf_symbol:
                logging.warning(f"Symbol {symbol} not in mapping")
                return None
            
            # Download data with 1-hour interval
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(
                start=start_time - timedelta(days=2),
                end=end_time + timedelta(hours=1),
                interval='1h'
            )
            
            if df.empty:
                logging.warning(f"No data for {yf_symbol}")
                return None
            
            # Standardize column names
            df = df.reset_index()
            df.columns = [col.lower() for col in df.columns]
            
            if 'datetime' in df.columns:
                df = df.rename(columns={'datetime': 'time'})
            
            return df
        
        except Exception as e:
            logging.error(f"Error fetching data for {symbol}: {e}")
            return None
    
    def get_atr(self, symbol: str, timestamp: datetime, period: int = ATR_PERIOD) -> Optional[float]:
        """Calculate ATR at a specific timestamp using MT5 or yfinance."""
        try:
            # Try MT5's built-in ATR if available
            if self.data_source == 'mt5' and self.mt5:
                atr = self.mt5.get_atr(symbol, timestamp, period)
                if atr is not None:
                    return atr
                # If MT5 ATR fails, continue to yfinance method below
            
            # Fallback: Calculate ATR using get_ticker_data
            end_time = timestamp + timedelta(hours=1)
            df = self.get_ticker_data(symbol, timestamp - timedelta(days=7), end_time)
            
            if df is None or len(df) < period:
                return None
            
            # Filter data up to timestamp
            df = df[df['time'] <= timestamp].tail(period + 10)
            
            if len(df) < period:
                return None
            
            # Calculate True Range
            df['high_low'] = df['high'] - df['low']
            df['high_close'] = abs(df['high'] - df['close'].shift())
            df['low_close'] = abs(df['low'] - df['close'].shift())
            df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
            
            # ATR is rolling mean of TR
            atr = df['tr'].rolling(period).mean().iloc[-1]
            return atr if not np.isnan(atr) else None
        
        except Exception as e:
            logging.error(f"Error calculating ATR for {symbol}: {e}")
            return None
    
    def get_price_at_timestamp(self, symbol: str, timestamp: datetime) -> Optional[float]:
        """Get close price at specific timestamp using MT5 or yfinance."""
        try:
            # Try MT5's built-in price lookup if available
            if self.data_source == 'mt5' and self.mt5:
                price = self.mt5.get_price_at_time(symbol, timestamp)
                if price is not None:
                    return price
                # If MT5 price lookup fails, continue to yfinance method below
            
            # Fallback: Get data around timestamp using get_ticker_data
            start = timestamp - timedelta(hours=2)
            end = timestamp + timedelta(hours=2)
            df = self.get_ticker_data(symbol, start, end)
            
            if df is None or df.empty:
                return None
            
            # Find closest price to timestamp
            df['time_diff'] = abs((df['time'] - timestamp).dt.total_seconds())
            closest_row = df.loc[df['time_diff'].idxmin()]
            
            return float(closest_row['close'])
        
        except Exception as e:
            logging.error(f"Error getting price for {symbol}: {e}")
            return None
    
    def get_future_prices(self, symbol: str, start_time: datetime, hours: int = SIMULATION_WINDOW_HOURS) -> Optional[pd.DataFrame]:
        """Get future price candles from start_time to start_time + hours."""
        try:
            end_time = start_time + timedelta(hours=hours)
            df = self.get_ticker_data(symbol, start_time, end_time)
            
            if df is None:
                return None
            
            # Filter to future prices only
            future_df = df[df['time'] >= start_time].copy()
            
            return future_df if not future_df.empty else None
        
        except Exception as e:
            logging.error(f"Error getting future prices for {symbol}: {e}")
            return None
    
    def simulate_outcome(
        self, 
        entry_price: float, 
        direction: str, 
        sl_price: float, 
        tp_price: float, 
        future_df: pd.DataFrame
    ) -> Tuple[Optional[str], Optional[float], Optional[float]]:
        """
        Simulate trade outcome.
        
        Returns:
            (outcome, exit_price, hours_to_exit)
            outcome: 'TP', 'SL', or 'OPEN'
        """
        if future_df is None or future_df.empty:
            return None, None, None
        
        direction = direction.upper()
        start_time = future_df.iloc[0]['time']
        
        for idx, row in future_df.iterrows():
            if direction == 'BUY':
                # Check TP first (take profit at high)
                if row['high'] >= tp_price:
                    hours_elapsed = (row['time'] - start_time).total_seconds() / 3600
                    return 'TP', tp_price, hours_elapsed
                # Then check SL (stop loss at low)
                if row['low'] <= sl_price:
                    hours_elapsed = (row['time'] - start_time).total_seconds() / 3600
                    return 'SL', sl_price, hours_elapsed
            else:  # SELL
                # For sell, TP is below entry, SL is above
                if row['low'] <= tp_price:
                    hours_elapsed = (row['time'] - start_time).total_seconds() / 3600
                    return 'TP', tp_price, hours_elapsed
                if row['high'] >= sl_price:
                    hours_elapsed = (row['time'] - start_time).total_seconds() / 3600
                    return 'SL', sl_price, hours_elapsed
        
        # Neither TP nor SL hit, position still open
        last_price = future_df.iloc[-1]['close']
        hours_elapsed = (future_df.iloc[-1]['time'] - start_time).total_seconds() / 3600
        return 'OPEN', last_price, hours_elapsed
    
    def calculate_pnl(
        self, 
        entry_price: float, 
        exit_price: float, 
        direction: str, 
        lot_size: float = 0.01
    ) -> float:
        """Calculate PnL in USD (simplified for crypto/forex)."""
        if direction.upper() == 'BUY':
            pnl = (exit_price - entry_price) * lot_size * 100000  # Standard lot
        else:
            pnl = (entry_price - exit_price) * lot_size * 100000
        
        return pnl
    
    def process_journal_file(self, filepath: Path):
        """Process a single journal file."""
        logging.info(f"📖 Processing: {filepath.name}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split by signal blocks
        lines = content.split('\n')
        new_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            new_lines.append(line)
            
            # Check if this is a HIVE PASSED signal
            if '✅ status:: hive_passed' in line:
                # Parse the signal block
                signal_data = self._parse_signal_block(lines, i)
                
                if signal_data and 'simulated_outcome' not in signal_data:
                    # Enrich this signal
                    enriched_lines = self._enrich_signal(signal_data)
                    if enriched_lines:
                        # Insert enriched lines after the current block
                        # Find the end of this block (next bullet or empty line)
                        j = i + 1
                        while j < len(lines) and lines[j].startswith('    '):
                            j += 1
                        
                        # Insert before moving to next block
                        new_lines.extend(enriched_lines)
                        i = j - 1  # Will be incremented at end of loop
            
            i += 1
        
        # Write back
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
    
    def _parse_signal_block(self, lines: List[str], start_idx: int) -> Optional[Dict]:
        """Parse a signal block starting at start_idx."""
        signal = {}
        i = start_idx
        
        while i < len(lines) and (lines[i].startswith('  -') or lines[i].startswith('    ')):
            line = lines[i].strip()
            
            # Extract properties
            if '::' in line:
                parts = line.split('::', 1)
                key = parts[0].strip()
                value = parts[1].strip()
                signal[key] = value
            
            i += 1
        
        # If this is a hive_passed signal without direction, look backward for the found signal
        if signal.get('status') == 'hive_passed' and 'direction' not in signal:
            symbol = signal.get('symbol', '').replace('[[', '').replace(']]', '')
            
            # Search backward for matching found signal (usually 1-3 entries before)
            search_idx = start_idx - 1
            max_lookback = 10  # Don't search too far back
            
            while search_idx >= max(0, start_idx - max_lookback):
                if '🔍 status:: found' in lines[search_idx]:
                    # Parse this found signal
                    found_signal = {}
                    j = search_idx
                    while j < len(lines) and (lines[j].startswith('  -') or lines[j].startswith('    ')):
                        line = lines[j].strip()
                        if '::' in line:
                            parts = line.split('::', 1)
                            key = parts[0].strip()
                            value = parts[1].strip()
                            found_signal[key] = value
                        j += 1
                    
                    # Check if it's the same symbol
                    found_symbol = found_signal.get('symbol', '').replace('[[', '').replace(']]', '')
                    if found_symbol == symbol and 'direction' in found_signal:
                        signal['direction'] = found_signal['direction']
                        break
                
                search_idx -= 1
        
        return signal if signal else None
    
    def _enrich_signal(self, signal: Dict) -> Optional[List[str]]:
        """Enrich a signal with simulated outcome."""
        try:
            # Extract required fields
            symbol = signal.get('symbol', '').replace('[[', '').replace(']]', '')
            timestamp_str = signal.get('timestamp', '')
            direction = signal.get('direction', '')
            
            if not all([symbol, timestamp_str, direction]):
                logging.warning(f"Missing required fields for {symbol}")
                return None
            
            # Parse timestamp
            timestamp = datetime.fromisoformat(timestamp_str)
            
            # Make timezone-aware (UTC) if naive
            if timestamp.tzinfo is None:
                import pytz
                timestamp = pytz.UTC.localize(timestamp)
            
            # Get entry price
            entry_price = self.get_price_at_timestamp(symbol, timestamp)
            if not entry_price:
                self.stats['data_unavailable'] += 1
                return ['    simulated_outcome:: DATA_UNAVAILABLE']
            
            # Get ATR
            atr = self.get_atr(symbol, timestamp)
            if not atr:
                self.stats['data_unavailable'] += 1
                return ['    simulated_outcome:: DATA_UNAVAILABLE']
            
            # Calculate SL/TP
            if direction.upper() == 'BUY':
                sl_price = entry_price - (SL_MULT * atr)
                tp_price = entry_price + (TP_MULT * atr)
            else:
                sl_price = entry_price + (SL_MULT * atr)
                tp_price = entry_price - (TP_MULT * atr)
            
            # Get future prices
            future_df = self.get_future_prices(symbol, timestamp)
            
            # Simulate outcome
            outcome, exit_price, hours = self.simulate_outcome(
                entry_price, direction, sl_price, tp_price, future_df
            )
            
            if not outcome:
                self.stats['data_unavailable'] += 1
                return ['    simulated_outcome:: DATA_UNAVAILABLE']
            
            # Calculate PnL
            pnl = self.calculate_pnl(entry_price, exit_price, direction)
            
            # Generate enrichment lines
            enriched = [
                f'    entry_price:: {entry_price:.2f}',
                f'    sl_price:: {sl_price:.2f}',
                f'    tp_price:: {tp_price:.2f}',
                f'    atr:: {atr:.2f}',
                f'    simulated_outcome:: {outcome}',
                f'    simulated_exit_price:: {exit_price:.2f}',
                f'    simulated_pnl:: ${pnl:.2f}',
                f'    hours_to_exit:: {hours:.1f}'
            ]
            
            self.stats['signals_enriched'] += 1
            logging.info(f"✅ Enriched {symbol} {direction}: {outcome} (${pnl:.2f})")
            
            return enriched
        
        except Exception as e:
            logging.error(f"Error enriching signal: {e}")
            self.stats['errors'] += 1
            return None
    
    def run(self):
        """Main execution."""
        # Process all journal files
        for journal_file in self.journals_dir.glob("*.md"):
            if journal_file.name.startswith('.'):
                continue
            
            try:
                self.process_journal_file(journal_file)
            except Exception as e:
                logging.error(f"Error processing {journal_file.name}: {e}")
        
        # Print summary
        print("\n" + "="*60)
        print("📊 ENRICHMENT SUMMARY")
        print("="*60)
        print(f"✅ Signals enriched: {self.stats['signals_enriched']}")
        print(f"⚠️  Data unavailable: {self.stats['data_unavailable']}")
        print(f"❌ Errors: {self.stats['errors']}")
        print("="*60 + "\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Enrich Logseq signals with yfinance outcomes")
    parser.add_argument(
        '--logseq',
        default='~/Desktop/Nanobot-Logseq',
        help='Logseq graph directory'
    )
    
    args = parser.parse_args()
    logseq_dir = os.path.expanduser(args.logseq)
    
    enricher = OutcomeEnricher(logseq_dir)
    enricher.run()


if __name__ == "__main__":
    main()
