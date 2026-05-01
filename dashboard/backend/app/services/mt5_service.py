import os
import json
import logging
import subprocess
import time
from typing import Optional, Dict, List
from siliconmetatrader5 import MetaTrader5

logger = logging.getLogger("DASHBOARD_MT5")

class MT5Service:
    def __init__(self, project_root: str, port: int = 18812):
        self.project_root = project_root
        self.port = port
        self.client = None
        self.creds_path = os.path.join(project_root, "config/credentials.json")
        self.mt5_data_path = os.path.expanduser("~/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5")

    def list_discovered_accounts(self) -> list:
        """Scans MT5 Bases directory to find previously used accounts/servers."""
        discovered = []
        bases_path = os.path.join(self.mt5_data_path, "Bases")
        
        if not os.path.exists(bases_path):
            return discovered
            
        # Scan servers (subdirectories in Bases)
        for server in os.listdir(bases_path):
            server_path = os.path.join(bases_path, server)
            if not os.path.isdir(server_path) or server in ["Default", "Custom", "signals"]:
                continue
                
            # Look for account IDs in 'trades' or 'mail'
            potential_accounts = set()
            trades_path = os.path.join(server_path, "trades")
            if os.path.exists(trades_path):
                for item in os.listdir(trades_path):
                    if item.isdigit():
                        potential_accounts.add(item)
            
            mail_path = os.path.join(server_path, "mail")
            if os.path.exists(mail_path):
                for item in os.listdir(mail_path):
                    # mail-123456.dat
                    if item.startswith("mail-") and item.endswith(".dat"):
                        acc_id = item.replace("mail-", "").replace(".dat", "")
                        if acc_id.isdigit():
                            potential_accounts.add(acc_id)
            
            for acc in potential_accounts:
                discovered.append({
                    "account": int(acc),
                    "server": server
                })
        
        return discovered

    def _load_creds(self) -> Optional[Dict]:
        if os.path.exists(self.creds_path):
            try:
                with open(self.creds_path, 'r') as f:
                    data = json.load(f)
                    return data.get("mt5")
            except Exception as e:
                logger.error(f"Error loading credentials: {e}")
        return None

    def _launch_mt5_app(self):
        """Opens MetaTrader 5 via macOS native 'open' command."""
        try:
            running = subprocess.check_output(["pgrep", "-f", "MetaTrader 5"], stderr=subprocess.DEVNULL).decode().strip()
            if running:
                logger.info("📡 MetaTrader 5 already running.")
                return
        except:
            pass
        logger.info("🖥️ Launching MetaTrader 5 app via macOS...")
        try:
            subprocess.Popen(["open", "-a", "MetaTrader 5"])
            time.sleep(10)  # Give MT5 time to fully load
        except Exception as e:
            logger.error(f"Failed to open MetaTrader 5: {e}")

    def _launch_bridge(self):
        """Launches the RPyC bridge server (python.exe rpyc_start.py) via Wine inside the MT5 Wine prefix."""
        # Check if port is already active
        try:
            output = subprocess.check_output(["lsof", "-i", f":{self.port}"], stderr=subprocess.DEVNULL).decode()
            if "LISTEN" in output:
                logger.info(f"📡 RPyC Bridge already listening on port {self.port}. Skipping launch.")
                return
        except:
            pass  # Port is free — proceed to launch

        wine_bin = "/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine64"
        wine_prefix = os.path.expanduser("~/Library/Application Support/net.metaquotes.wine.metatrader5")
        mt5_dir = os.path.join(wine_prefix, "drive_c/Program Files/MetaTrader 5")
        python_exe = "C:\\Program Files\\MetaTrader 5\\python.exe"
        rpyc_script = "C:\\Program Files\\MetaTrader 5\\rpyc_start.py"

        if not os.path.exists(wine_bin):
            logger.warning("Wine binary not found. Using macOS open fallback.")
            self._launch_mt5_app()
            return

        env = os.environ.copy()
        env["WINEPREFIX"] = wine_prefix
        env["WINEDEBUG"] = "-all"  # Suppress Wine debug noise

        logger.info("🚀 Launching RPyC Bridge (python.exe rpyc_start.py via Wine)...")
        try:
            subprocess.Popen(
                [wine_bin, python_exe, rpyc_script],
                env=env,
                cwd=mt5_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            # Wait actively for port to open (up to 20s)
            for i in range(20):
                time.sleep(1)
                try:
                    out = subprocess.check_output(["lsof", "-i", f":{self.port}"], stderr=subprocess.DEVNULL).decode()
                    if "LISTEN" in out:
                        logger.info(f"✅ RPyC Bridge is now listening on port {self.port} (after {i+1}s).")
                        return
                except:
                    pass
            logger.warning(f"⚠️ Bridge did not start listening within 20s on port {self.port}.")
        except Exception as e:
            logger.error(f"Failed to launch RPyC bridge: {e}")

    def connect(self, force: bool = False):
        """Connects to MT5, reusing the active Wine session if possible."""
        creds = self._load_creds()
        target_login = int(creds.get("account", 0)) if creds else 0
        target_server = creds.get("server", "") if creds else ""
        password = creds.get("password", "") if creds else ""

        # Reuse existing healthy client
        if self.client and not force:
            try:
                info = self.client.account_info()
                if info:
                    logger.info(f"♻️ Reusing active MT5 session: #{info.login} | Balance: {info.balance}")
                    return True
            except:
                self.client = None

        try:
            if not self.client:
                self.client = MetaTrader5(port=self.port)

            # STRATEGY 1: Bare initialize — reuse whatever is already logged in the terminal
            logger.info("🔑 MT5 Strategy 1: Bare initialize (reuse active session)...")
            if self.client.initialize():
                info = self.client.account_info()
                if info:
                    logger.info(f"✅ MT5 Connected (bare): #{info.login} on {info.server} | Balance: {info.balance}")
                    return True

            # STRATEGY 2: Initialize with login/server only (no password — terminal has saved creds)
            if target_login:
                logger.warning(f"Strategy 1 failed: {self.client.last_error()}. Trying with account params...")
                init_params = {"login": target_login, "server": target_server}
                if password:
                    init_params["password"] = password

                if self.client.initialize(**init_params):
                    logger.info(f"✅ MT5 Connected (with params): #{target_login}")
                    return True

            # STRATEGY 3: Launch RPyC bridge and retry bare
            logger.warning(f"Strategy 2 failed: {self.client.last_error()}. Launching bridge...")
            self._launch_bridge()

            if self.client.initialize():
                info = self.client.account_info()
                if info:
                    logger.info(f"✅ MT5 Connected after bridge launch: #{info.login}")
                    return True

        except Exception as e:
            logger.error(f"MT5 Connection error: {e}")
            self.client = None

        logger.error("❌ MT5: All connection strategies failed.")
        return False

    def get_account_stats(self):

        if not self.connect():
            return None
        
        try:
            acc_info = self.client.account_info()
            positions = self.client.positions_get()
            
            # Fetch closed profit for today
            from datetime import datetime, time as dtime
            now = datetime.now()
            start_of_day = datetime.combine(now.date(), dtime.min)
            
            deals = self.client.history_deals_get(start_of_day, now)
            closed_profit = 0.0
            if deals:
                for d in deals:
                    # Entry=1 (Entry Out) or Entry=2 (Entry In/Out) usually signifies a closing or profit-booking event
                    # But the simplest is just summing the 'profit' field of all deals today
                    closed_profit += d.profit
            
            if acc_info:
                return {
                    "balance": acc_info.balance,
                    "equity": acc_info.equity,
                    "margin": acc_info.margin,
                    "free_margin": acc_info.margin_free,
                    "margin_level": acc_info.margin_level,
                    "floating_profit": acc_info.profit,
                    "closed_profit": closed_profit,
                    "daily_pnl": acc_info.profit + closed_profit,
                    "active_trades": len(positions) if positions else 0,
                    "active_positions": self.get_active_positions(),
                    "trade_history": self.get_trade_history(),
                    "last_log_lines": self.get_last_logs(20)
                }
        except Exception as e:
            logger.error(f"Error fetching account stats: {e}")
        
        return None

    def get_active_positions(self) -> List[Dict]:
        """Fetch detailed info for all open positions."""
        if not self.connect(): return []
        positions = self.client.positions_get()
        if not positions: return []
        
        return [{
            "ticket": p.ticket,
            "symbol": p.symbol,
            "type": "BUY" if p.type == 0 else "SELL",
            "volume": p.volume,
            "price_open": p.price_open,
            "price_current": p.price_current,
            "profit": p.profit,
            "time_open": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(p.time))
        } for p in positions]

    def get_trade_history(self) -> List[Dict]:
        """Fetch history of closed trades for today."""
        if not self.connect(): return []
        from datetime import datetime, time as dtime
        now = datetime.now()
        start_of_day = datetime.combine(now.date(), dtime.min)
        
        deals = self.client.history_deals_get(start_of_day, now)
        if not deals: return []
        
        history = []
        for d in deals:
            # We only want entries that represent closing (Entry Out) 
            # or just all deals with profit != 0
            if d.profit != 0:
                history.append({
                    "ticket": d.ticket,
                    "symbol": d.symbol,
                    "type": "FIX" if d.entry == 0 else "OUT", # Simplified
                    "volume": d.volume,
                    "price_open": 0.0, # Not directly in deal info
                    "price_current": d.price,
                    "profit": d.profit,
                    "time_open": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(d.time))
                })
        return history[-20:] # Last 20 closed deals

    def get_last_logs(self, limit: int = 50) -> List[str]:
        """Fetch last lines from dashboard_bot.log."""
        log_path = os.path.join(self.project_root, "logs/dashboard_bot.log")
        if not os.path.exists(log_path):
            return ["Log file not found."]
        
        try:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
                return [line.strip() for line in lines[-limit:]]
        except Exception as e:
            return [f"❌ Error reading logs: {str(e)}"]

    def get_recent_signals(self):
        # This will be integrated with the bot's signal logging later
        # For now, it's a placeholder for current signals detecting by MT5
        return []
