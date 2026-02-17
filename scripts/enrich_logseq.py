#!/usr/bin/env python3
"""
Nanobot Logs to Logseq Automation
Automatically converts Nanobot trading logs into Logseq Markdown format.

Author: Nanobot Team
Version: 1.0.0
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import argparse


class LogseqExporter:
    """Export Nanobot trading logs to Logseq graph format."""
    
    def __init__(self, logs_dir: str, logseq_dir: str, config_file: Optional[str] = None):
        """
        Initialize the exporter.
        
        Args:
            logs_dir: Directory containing Nanobot log files
            logseq_dir: Root directory of Logseq graph
            config_file: Optional JSON config file with custom parsing rules
        """
        self.logs_dir = Path(logs_dir)
        self.logseq_dir = Path(logseq_dir)
        self.journals_dir = self.logseq_dir / "journals"
        self.pages_dir = self.logseq_dir / "pages"
        
        # Create directories if they don't exist
        self.journals_dir.mkdir(parents=True, exist_ok=True)
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        
        # Track processed trades to avoid duplicates
        self.processed_file = self.logseq_dir / ".nanobot_processed.json"
        self.processed_trades = self._load_processed()
        
        # Statistics
        self.stats = {
            'new_trades': 0,
            'rejected_signals': 0,
            'updated_journals': set(),
            'updated_pages': set()
        }
        
    def _load_processed(self) -> set:
        """Load set of already processed trade IDs."""
        if self.processed_file.exists():
            with open(self.processed_file, 'r') as f:
                return set(json.load(f))
        return set()
    
    def _save_processed(self):
        """Save processed trade IDs to disk."""
        with open(self.processed_file, 'w') as f:
            json.dump(list(self.processed_trades), f, indent=2)
    
    def parse_trade_line(self, line: str, file_date: Optional[str] = None) -> Optional[Dict]:
        """
        Parse a trade line from Nanobot logs.
        
        Supported formats (Real Nanobot):
        - 17:48:21 | INFO | 🔍 [1/5] SIGNAL FOUND: USDCAD (BUY)
        - 17:48:21 | INFO | 🚫 [2/5] HIVE REJECTED: USDCAD (ADX=11.4, Vol=0.3)
        - 20:58:07 | INFO | ✅ [2/5] HIVE PASSED: AUDUSD (ADX=16.6, Vol=0.6)
        - 21:00:32 | WARNING | ⚖️ [5/7] KELLY SKIP: USDJPY No mathematical edge detected (f* <= 0).
        
        Returns:
            Dict with trade info or None if line doesn't match
        """
        # Extract date from line if present, otherwise use date from log filename
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', line)
        date = date_match.group(1) if date_match else file_date or "unknown"
        
        # Pattern 1: SIGNAL FOUND
        signal_pattern = r'(\d{2}:\d{2}:\d{2})\s+\|\s+INFO\s+\|\s+🔍\s+\[1/5\]\s+SIGNAL FOUND:\s+(\w+)\s+\((\w+)\)'
        match = re.search(signal_pattern, line)
        
        if match:
            time, symbol, direction = match.groups()
            
            return {
                'type': 'signal',
                'status': 'found',
                'date': date,
                'time': time,
                'datetime': f"{date}T{time}" if date != "unknown" else time,
                'direction': direction.upper(),
                'symbol': symbol,
                'reason': 'EMA crossover detected',
                'id': f"{date}_{time}_{symbol}_{direction}_signal"
            }
        
        # Pattern 2: HIVE REJECTED
        reject_pattern = r'(\d{2}:\d{2}:\d{2})\s+\|\s+INFO\s+\|\s+🚫\s+\[2/5\]\s+HIVE REJECTED:\s+(\w+)\s+\(ADX=([\d.]+),\s+Vol=([\d.]+)\)'
        match = re.search(reject_pattern, line)
        
        if match:
            time, symbol, adx, vol = match.groups()
            
            return {
                'type': 'signal',
                'status': 'rejected',
                'date': date,
                'time': time,
                'datetime': f"{date}T{time}" if date != "unknown" else time,
                'symbol': symbol,
                'reason': f'HIVE Filter (ADX={adx}, Vol={vol})',
                'adx': float(adx),
                'volatility': float(vol),
                'id': f"{date}_{time}_{symbol}_hive_rejected"
            }
        
        # Pattern 3: HIVE PASSED
        passed_pattern = r'(\d{2}:\d{2}:\d{2})\s+\|\s+INFO\s+\|\s+✅\s+\[2/5\]\s+HIVE PASSED:\s+(\w+)\s+\(ADX=([\d.]+),\s+Vol=([\d.]+)\)'
        match = re.search(passed_pattern, line)
        
        if match:
            time, symbol, adx, vol = match.groups()
            
            return {
                'type': 'signal',
                'status': 'hive_passed',
                'date': date,
                'time': time,
                'datetime': f"{date}T{time}" if date != "unknown" else time,
                'symbol': symbol,
                'reason': f'HIVE Passed (ADX={adx}, Vol={vol})',
                'adx': float(adx),
                'volatility': float(vol),
                'id': f"{date}_{time}_{symbol}_hive_passed"
            }
        
        # Pattern 4: MARKET REGIME
        regime_pattern = r'(\d{2}:\d{2}:\d{2})\s+\|\s+INFO\s+\|\s+📊\s+\[3/6\]\s+MARKET REGIME:\s+(\w+)\s+is\s+(TRENDING|RANGING)'
        match = re.search(regime_pattern, line)
        
        if match:
            time, symbol, regime = match.groups()
            return {
                'type': 'metadata',
                'category': 'regime',
                'date': date,
                'time': time,
                'symbol': symbol,
                'regime': regime
            }
        
        # Pattern 5: KELLY ENGINE
        kelly_pattern = r'(\d{2}:\d{2}:\d{2})\s+\|\s+INFO\s+\|\s+⚖️\s+\[KELLY\]\s+p=([\d.]+)\s+\(SE=([\d.]+)\)\s+\|\s+f\*=([\d.]+)\s+\|.*?Mult=([\d.]+)x'
        match = re.search(kelly_pattern, line)
        
        if match:
            time, prob, se, f_star, mult = match.groups()
            return {
                'type': 'metadata',
                'category': 'kelly',
                'date': date,
                'time': time,
                'ml_probability': float(prob),
                'ml_standard_error': float(se),
                'kelly_f_star': float(f_star),
                'kelly_mult': float(mult)
            }
        
        # Pattern 6: KELLY SKIP
        kelly_skip_pattern = r'(\d{2}:\d{2}:\d{2})\s+\|\s+WARNING\s+\|\s+⚖️\s+\[5/7\]\s+KELLY SKIP:\s+(\w+)\s+(.+)'
        match = re.search(kelly_skip_pattern, line)
        
        if match:
            time, symbol, reason = match.groups()
            
            return {
                'type': 'signal',
                'status': 'kelly_skip',
                'date': date,
                'time': time,
                'datetime': f"{date}T{time}" if date != "unknown" else time,
                'symbol': symbol,
                'reason': f'Kelly Skip: {reason.strip()}',
                'id': f"{date}_{time}_{symbol}_kelly_skip"
            }
        
        return None
    
    def process_logs(self, full_rebuild: bool = False):
        """
        Process all log files and extract trades.
        
        Args:
            full_rebuild: If True, ignore processed trades and rebuild everything
        """
        if full_rebuild:
            self.processed_trades.clear()
        
        # Data structures
        trades_by_date = defaultdict(list)
        trades_by_symbol = defaultdict(list)
        
        # Find all log files
        log_files = sorted(self.logs_dir.glob("trading_*.log"))
        
        print(f"📂 Found {len(log_files)} log files in {self.logs_dir}")
        
        for log_file in log_files:
            # Extract date from filename: trading_20260216.log -> 2026-02-16
            filename_match = re.search(r'trading_(\d{4})(\d{2})(\d{2})\.log', log_file.name)
            file_date = None
            if filename_match:
                year, month, day = filename_match.groups()
                file_date = f"{year}-{month}-{day}"
            
            print(f"📖 Processing: {log_file.name} (date: {file_date})")
            
            # Temporary storage for metadata to enrich signals
            recent_metadata = {}  # {symbol: {kelly: {...}, regime: ...}}
            
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    parsed = self.parse_trade_line(line, file_date)
                    
                    if not parsed:
                        continue
                    
                    # Handle metadata (Kelly, Regime)
                    if parsed.get('type') == 'metadata':
                        category = parsed.get('category')
                        
                        # Build key from time (assume metadata is right after signal)
                        # We'll match by timestamp proximity
                        time_key = parsed['time']
                        
                        if category == 'kelly':
                            # Store Kelly metadata
                            if time_key not in recent_metadata:
                                recent_metadata[time_key] = {}
                            recent_metadata[time_key]['kelly'] = {
                                'ml_probability': parsed['ml_probability'],
                                'ml_standard_error': parsed['ml_standard_error'],
                                'kelly_f_star': parsed['kelly_f_star'],
                                'kelly_mult': parsed['kelly_mult']
                            }
                        elif category == 'regime':
                            # Store regime metadata
                            symbol = parsed['symbol']
                            if time_key not in recent_metadata:
                                recent_metadata[time_key] = {}
                            recent_metadata[time_key]['regime'] = parsed['regime']
                            recent_metadata[time_key]['symbol'] = symbol
                        
                        continue
                    
                    # Handle signals
                    if parsed.get('type') == 'signal':
                        trade = parsed
                        trade_id = trade['id']
                        
                        # Skip if already processed
                        if trade_id in self.processed_trades:
                            continue
                        
                        # Enrich with metadata if available
                        time_key = trade['time']
                        if time_key in recent_metadata:
                            meta = recent_metadata[time_key]
                            
                            # Add Kelly data
                            if 'kelly' in meta:
                                trade.update(meta['kelly'])
                            
                            # Add Regime data
                            if 'regime' in meta:
                                trade['regime'] = meta['regime']
                        
                        # Add to data structures
                        trades_by_date[trade['date']].append(trade)
                        trades_by_symbol[trade['symbol']].append(trade)
                        
                        # Mark as processed
                        self.processed_trades.add(trade_id)
                        
                        # Update stats
                        if trade['status'] == 'hive_passed':
                            self.stats['new_trades'] += 1
                        else:
                            self.stats['rejected_signals'] += 1
        
        # Generate Markdown files
        self._generate_journals(trades_by_date)
        self._generate_symbol_pages(trades_by_symbol)
        
        # Save processed IDs
        self._save_processed()
    
    def _generate_journals(self, trades_by_date: Dict[str, List[Dict]]):
        """Generate daily journal entries."""
        for date, trades in trades_by_date.items():
            # Convert date format: 2026-02-17 -> 2026_02_17
            journal_name = date.replace('-', '_') + '.md'
            journal_path = self.journals_dir / journal_name
            
            # Read existing content if file exists
            existing_content = ""
            if journal_path.exists():
                with open(journal_path, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
            
            # Generate new trade entries
            new_content = self._format_journal_trades(trades, date)
            
            # Merge with existing content
            if "<!-- NANOBOT GENERATED START -->" in existing_content:
                # Replace generated section
                parts = existing_content.split("<!-- NANOBOT GENERATED START -->")
                before = parts[0]
                after_parts = parts[1].split("<!-- NANOBOT GENERATED END -->")
                after = after_parts[1] if len(after_parts) > 1 else ""
                
                final_content = f"{before}<!-- NANOBOT GENERATED START -->\n{new_content}\n<!-- NANOBOT GENERATED END -->{after}"
            else:
                # Append to end
                final_content = f"{existing_content}\n<!-- NANOBOT GENERATED START -->\n{new_content}\n<!-- NANOBOT GENERATED END -->\n"
            
            # Write file
            with open(journal_path, 'w', encoding='utf-8') as f:
                f.write(final_content)
            
            self.stats['updated_journals'].add(journal_name)
            print(f"  ✅ Updated journal: {journal_name} ({len(trades)} entries)")
    
    def _format_journal_trades(self, trades: List[Dict], date: str) -> str:
        """Format trades for journal entry."""
        lines = ["- ## 🦖 Operaciones Nanobot\n"]
        
        for trade in sorted(trades, key=lambda x: x['time']):
            # Determine emoji based on status
            if trade['status'] == 'hive_passed':
                emoji = "✅"
            elif trade['status'] == 'kelly_skip':
                emoji = "⚖️"
            elif trade['status'] == 'found':
                emoji = "🔍"
            else:
                emoji = "🚫"
            
            lines.append(f"  - {emoji} status:: {trade['status']}")
            lines.append(f"    symbol:: [[{trade['symbol']}]]")
            
            # Add direction if available
            if 'direction' in trade:
                lines.append(f"    direction:: {trade['direction']}")
            
            # Add reason
            lines.append(f"    reason:: {trade['reason']}")
            lines.append(f"    time:: {trade['time']}")
            
            # Add metrics if available
            if 'adx' in trade:
                lines.append(f"    adx:: {trade['adx']:.1f}")
            if 'volatility' in trade:
                lines.append(f"    volatility:: {trade['volatility']:.1f}")
            
            # Add ML/Kelly data if available  
            if 'ml_probability' in trade:
                lines.append(f"    ml_probability:: {trade['ml_probability']:.3f}")
            if 'ml_standard_error' in trade:
                lines.append(f"    ml_se:: {trade['ml_standard_error']:.3f}")
            if 'kelly_mult' in trade:
                lines.append(f"    kelly_mult:: {trade['kelly_mult']:.2f}x")
            if 'kelly_f_star' in trade:
                lines.append(f"    kelly_f:: {trade['kelly_f_star']:.4f}")
            
            # Add regime if available
            if 'regime' in trade:
                lines.append(f"    regime:: {trade['regime']}")
            
            # Add timestamp
            if 'datetime' in trade:
                lines.append(f"    timestamp:: {trade['datetime']}")
        
        return '\n'.join(lines)
    
    def _generate_symbol_pages(self, trades_by_symbol: Dict[str, List[Dict]]):
        """Generate symbol pages with all trades for each symbol."""
        for symbol, trades in trades_by_symbol.items():
            page_path = self.pages_dir / f"{symbol}.md"
            
            # Group trades by date
            trades_by_date = defaultdict(list)
            for trade in trades:
                if trade['status'] == 'executed':
                    trades_by_date[trade['date']].append(trade)
            
            # Generate content
            lines = [f"- ## 📊 Historial de Trades - {symbol}\n"]
            
            # Sort dates descending (most recent first)
            for date in sorted(trades_by_date.keys(), reverse=True):
                date_trades = trades_by_date[date]
                total_pnl = sum(t['pnl'] for t in date_trades)
                pnl_emoji = "💰" if total_pnl > 0 else "📉"
                
                # Link to journal
                journal_link = date.replace('-', '_')
                lines.append(f"  - {pnl_emoji} [[{journal_link}]]")
                lines.append(f"    total_pnl:: ${total_pnl:.2f}")
                lines.append(f"    trades:: {len(date_trades)}")
                
                for trade in date_trades:
                    lines.append(f"      - {trade['direction']} | Vol: {trade['volume']} | PnL: ${trade['pnl']:.2f}")
            
            # Write file
            with open(page_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            
            self.stats['updated_pages'].add(f"{symbol}.md")
            print(f"  ✅ Updated page: {symbol}.md")
    
    def print_summary(self):
        """Print processing summary."""
        print("\n" + "="*60)
        print("📊 RESUMEN DE PROCESAMIENTO")
        print("="*60)
        print(f"✅ Nuevos trades: {self.stats['new_trades']}")
        print(f"⛔ Señales rechazadas: {self.stats['rejected_signals']}")
        print(f"📝 Journals actualizados: {len(self.stats['updated_journals'])}")
        print(f"📄 Páginas actualizadas: {len(self.stats['updated_pages'])}")
        print(f"💾 Total procesados (histórico): {len(self.processed_trades)}")
        print("="*60 + "\n")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Export Nanobot trading logs to Logseq format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process new logs incrementally
  python nanobot_to_logseq.py
  
  # Full rebuild from scratch
  python nanobot_to_logseq.py --full
  
  # Custom directories
  python nanobot_to_logseq.py --logs ./logs --logseq ~/Logseq/Nanobot
        """
    )
    
    parser.add_argument(
        '--logs',
        default='./logs',
        help='Directory containing Nanobot log files (default: ./logs)'
    )
    
    parser.add_argument(
        '--logseq',
        default='~/Logseq/Nanobot',
        help='Root directory of Logseq graph (default: ~/Logseq/Nanobot)'
    )
    
    parser.add_argument(
        '--full',
        action='store_true',
        help='Full rebuild: reprocess all logs ignoring previous state'
    )
    
    parser.add_argument(
        '--config',
        help='Custom JSON config file for advanced parsing rules'
    )
    
    args = parser.parse_args()
    
    # Expand user path
    logseq_dir = os.path.expanduser(args.logseq)
    
    print("🦖 NANOBOT TO LOGSEQ EXPORTER")
    print(f"📂 Logs directory: {args.logs}")
    print(f"📓 Logseq graph: {logseq_dir}")
    print(f"🔄 Mode: {'Full rebuild' if args.full else 'Incremental'}\n")
    
    # Create exporter
    exporter = LogseqExporter(args.logs, logseq_dir, args.config)
    
    # Process logs
    exporter.process_logs(full_rebuild=args.full)
    
    # Print summary
    exporter.print_summary()


if __name__ == "__main__":
    main()
