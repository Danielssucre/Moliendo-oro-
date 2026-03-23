import os
import sys
import logging
from typing import Dict, List, Optional
import re

# Add project root to path to import BinanceClient
PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/Users/danielsuarezsucre/TRADING/trading_agent")
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from src.nanobot.exchanges.binance_client import BinanceClient

logger = logging.getLogger("DASHBOARD_BINANCE")

class BinanceService:
    def __init__(self, project_root: str):
        self.project_root = project_root
        try:
            self.client = BinanceClient()
            logger.info("✅ PolimataService: Client initialized successfully")
        except Exception as e:
            logger.error(f"❌ BinanceService: Failed to initialize client: {e}")
            self.client = None

    def get_stats(self) -> Dict:
        """Fetch live stats from Binance + local bot logs."""
        if not self.client:
            return {
                "account_type": "N/A",
                "can_trade": False,
                "balances": {},
                "prices": {},
                "active_positions": [],
                "last_log_lines": ["❌ Binance Client Not Initialized"]
            }

        try:
            status = self.client.account_status()
            prices = {
                "BTC": self.client.get_price("BTCUSD"),
                "ETH": self.client.get_price("ETHUSD"),
                "SOL": self.client.get_price("SOLUSD")
            }
            
            # For Spot, we simulate 'positions' by looking at non-zero balances 
            # OR we could parse the local bot logs to find what was actually bought.
            # For now, let's just return balances and last log lines.
            
            log_lines = self.get_last_logs(20)
            
            return {
                "account_type": status["account_type"],
                "can_trade": status["can_trade"],
                "balances": status["balances"],
                "prices": prices,
                "active_positions": self._parse_active_positions(log_lines),
                "last_log_lines": log_lines
            }
        except Exception as e:
            logger.error(f"Error fetching Binance stats: {e}")
            return {
                "account_type": "Error",
                "can_trade": False,
                "balances": {},
                "prices": {},
                "active_positions": [],
                "last_log_lines": [f"❌ Error: {str(e)}"]
            }

    def _parse_active_positions(self, log_lines: List[str]) -> List[Dict]:
        """Attempt to extract current open positions from logs."""
        positions = []
        # pattern 1: ⏳ Active Positions: ['SOLUSDT'] (Legacy)
        # pattern 2: ✅ Recovered SOLUSDT @ $89.21 (Slot 1) (Polimata)
        # pattern 3: ✅ POSITION OPENED: ETHUSDT 0.05 @ $2500.00 (Polimata)
        
        pos_pattern = re.compile(r"⏳ Active Positions: \[(.*)\]")
        recovery_pattern = re.compile(r"✅ Recovered (\w+) @ \$(\d+\.\d+)")
        opened_pattern = re.compile(r"✅ POSITION OPENED: (\w+)\s+([\d\.]+)\s+@\s+\$([\d\.]+)")
        # Pattern for "🟢 BUY 0.07 SOLUSDT | OrderId: ..."
        buy_pattern = re.compile(r"🟢 BUY [\d\.]+ (\w+) \| OrderId:")
        # Pattern for "--- POLIMATA CYCLE ... | [active_symbols] ---"
        cycle_pattern = re.compile(r"--- POLIMATA CYCLE.*\|.*\| \[(.*)\] ---")

        for line in reversed(log_lines):
            # Try Recovery
            rec_match = recovery_pattern.search(line)
            if rec_match:
                positions.append({
                    "symbol": rec_match.group(1),
                    "entry": float(rec_match.group(2)),
                    "current": 0.0, "qty": 0.0, "pnl_pct": 0.0, "pnl_usdt": 0.0
                })
                continue
                
            # Try Opened
            op_match = opened_pattern.search(line)
            if op_match:
                positions.append({
                    "symbol": op_match.group(1),
                    "entry": float(op_match.group(3)),
                    "qty": float(op_match.group(2)),
                    "current": 0.0, "pnl_pct": 0.0, "pnl_usdt": 0.0
                })
                continue

            # Try Cycle Header (Most reliable current state)
            c_match = cycle_pattern.search(line)
            if c_match:
                syms = c_match.group(1).replace("'", "").split(", ")
                seen = set()
                for s in syms:
                    s = s.strip()
                    if s and s != "None" and s not in seen:
                        positions.append({"symbol": s, "entry": 0.0, "current": 0.0, "qty": 0.0, "pnl_pct": 0.0, "pnl_usdt": 0.0})
                        seen.add(s)
                return positions # Return immediately as this is the latest full state
                
            # Try Buy Match
            b_match = buy_pattern.search(line)
            if b_match:
                positions.append({
                    "symbol": b_match.group(1),
                    "entry": 0.0, "current": 0.0, "qty": 0.0, "pnl_pct": 0.0, "pnl_usdt": 0.0
                })
                continue

            # Try Legacy
            match = pos_pattern.search(line)
            if match:
                syms = match.group(1).replace("'", "").split(", ")
                for s in syms:
                    if s and s != "None":
                        positions.append({"symbol": s, "entry": 0.0, "current": 0.0, "qty": 0.0, "pnl_pct": 0.0, "pnl_usdt": 0.0})
                break
        return positions

    def get_last_logs(self, limit: int = 20) -> List[str]:
        """Fetch last N lines from polimata_binance.log or fallback."""
        paths = [
            os.path.join(self.project_root, "logs/polimata_binance.log"),
            os.path.join(self.project_root, "logs/skypie_binance.log")
        ]
        
        log_path = None
        for p in paths:
            if os.path.exists(p):
                log_path = p
                break
                
        if not log_path:
            return ["Log file not found."]
        
        try:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
                return [line.strip() for line in lines[-limit:]]
        except Exception as e:
            return [f"❌ Error reading logs: {str(e)}"]
