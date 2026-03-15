import os
import json
import logging
import subprocess
import time
from typing import Optional, Dict
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

    def _launch_bridge(self):
        """Launches the hijacked MetaEditor bridge via Wine."""
        # Simple check: is port already being listened on or bridge process exists?
        try:
            # Check if anyone is LISTENING on the port
            output = subprocess.check_output(["lsof", "-i", f":{self.port}"]).decode()
            if "LISTEN" in output:
                logger.info("📡 Bridge already listening. Skipping launch.")
                return
        except subprocess.CalledProcessError:
            pass # Port is clear

        wine_bin = "/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine64"
        wine_prefix = os.path.expanduser("~/Library/Application Support/net.metaquotes.wine.metatrader5")
        exe_path = "C:\\Program Files\\MetaTrader 5\\metaeditor64.exe"
        
        if not os.path.exists(wine_bin):
            logger.error("Wine binary not found in MT5 app bundle")
            return
            
        env = os.environ.copy()
        env["WINEPREFIX"] = wine_prefix
        
        logger.info("🚀 Launching MT5 IDE Bridge (MetaEditor Hijack)...")
        try:
            # We use nohup/subprocess to detach it
            subprocess.Popen(
                [wine_bin, exe_path],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
        except Exception as e:
            logger.error(f"Failed to launch bridge: {e}")

    def connect(self, force: bool = False):
        """Connects to MT5, ensuring the correct account is active."""
        creds = self._load_creds()
        if not creds:
            return False

        target_login = int(creds.get("account", 0))
        target_server = creds.get("server", "")
        password = creds.get("password", "")

        if self.client and not force:
            try:
                # Check health AND if it's the right account
                info = self.client.account_info()
                if info and info.login == target_login:
                    logger.info(f"♻️ Reusing existing session for {target_login}")
                    return True
                else:
                    logger.info(f"🔄 Account mismatch (Current: {info.login if info else 'None'}, Target: {target_login}). Reconnecting...")
                    self.client.shutdown()
                    self.client = None
            except:
                self.client = None

        try:
            if not self.client:
                self.client = MetaTrader5(port=self.port)
            
            logger.info(f"🔑 MT5 Attempting Connect: Account={target_login}, Server={target_server}")
            path = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
            
            # Initialization parameters
            init_params = {
                "login": target_login,
                "server": target_server
            }
            if password:
                init_params["password"] = password

            # Strategy 1: Attempt initialization with parameters
            # If no password provided, it relies on saved credentials in the terminal
            if self.client.initialize(path=path, portable=True, **init_params):
                logger.info(f"✅ MT5 Initialized: {target_login} on {target_server}")
                return True
            
            # Strategy 2: Fallback - Initialize WITHOUT path (reusing running terminal)
            logger.warning(f"MT5 initialize with path failed: {self.client.last_error()}. Trying fallback...")
            if self.client.initialize(**init_params):
                logger.info(f"✅ MT5 Initialized via Fallback: {target_login}")
                return True
                
            # Strategy 3: Launch bridge and try again
            logger.warning(f"MT5 fallback failed. Launching bridge...")
            self._launch_bridge()
            time.sleep(8)
            
            if self.client.initialize(**init_params):
                logger.info(f"✅ MT5 Initialized after bridge launch: {target_login}")
                return True
        except Exception as e:
            logger.error(f"MT5 Connection error: {e}")
            self.client = None
        
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
                    "active_trades": len(positions) if positions else 0
                }
        except Exception as e:
            logger.error(f"Error fetching account stats: {e}")
        
        return None

    def get_recent_signals(self):
        # This will be integrated with the bot's signal logging later
        # For now, it's a placeholder for current signals detecting by MT5
        return []
