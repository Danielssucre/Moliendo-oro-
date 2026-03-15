import subprocess
import psutil
import os
import json
import signal
from typing import Optional
from datetime import datetime

class BotManager:
    def __init__(self, project_root: str, mt5_service=None):
        self.project_root = project_root
        self.mt5_service = mt5_service
        self.script_path = os.path.join(project_root, "src/scripts/run_live.py")
        self.venv_python = os.path.join(project_root, ".venv/bin/python")
        self.log_file = os.path.join(project_root, "logs/dashboard_bot.log")

    def get_running_bot(self) -> Optional[psutil.Process]:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and self.script_path in proc.info['cmdline']:
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None

    def start_bot(self, capital: float = 100000):
        if self.get_running_bot():
            return {"status": "error", "message": "Bot is already running"}
        
        # Start bot in background
        cmd = [self.venv_python, self.script_path, "--capital", str(capital)]
        env = os.environ.copy()
        env["PYTHONPATH"] = self.project_root
        
        with open(self.log_file, "a") as f:
            proc = subprocess.Popen(
                cmd, 
                cwd=self.project_root, 
                stdout=f, 
                stderr=subprocess.STDOUT,
                env=env,
                preexec_fn=os.setsid
            )
        
        return {"status": "success", "pid": proc.pid}

    def stop_bot(self):
        proc = self.get_running_bot()
        if not proc:
            return {"status": "error", "message": "Bot is not running"}
        
        try:
            # Kill process group
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            return {"status": "success", "message": "Bot stopped"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_status(self):
        proc = self.get_running_bot()
        
        # Check MT5 Actual connection
        account_status = "Disconnected"
        if self.mt5_service and self.mt5_service.connect():
            account_status = "Active"
            
        # Check Telegram Status
        tg_status = "Not Configured"
        creds_path = os.path.join(self.project_root, "config/api_keys.json")
        if os.path.exists(creds_path):
            try:
                with open(creds_path, 'r') as f:
                    api_keys = json.load(f)
                    tg = api_keys.get("telegram", {})
                    if tg.get("bot_token") and tg.get("chat_id"):
                        tg_status = "Connected"
                    else:
                        tg_status = "Missing Config"
            except:
                tg_status = "Read Error"

        # Check Mega Grid Status from config
        mega_grid_active = True
        config_path = os.path.join(self.project_root, "config/trading_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    mega_grid_active = config.get("mega_grid_enabled", True)
            except: pass

        # Check Polimata Intel
        p_count = 0
        p_last = None
        intel_path = os.path.join(self.project_root, "config/polimata_intel.json")
        if os.path.exists(intel_path):
            try:
                with open(intel_path, 'r') as f:
                    intel = json.load(f)
                    p_count = intel.get("retrain_count", 0)
                    p_last = intel.get("last_retrain_date")
            except: pass

        status_data = {
            "is_running": proc is not None,
            "pid": proc.pid if proc else None,
            "uptime": str(datetime.now() - datetime.fromtimestamp(proc.create_time())) if proc else None,
            "account_status": account_status,
            "telegram_status": tg_status,
            "mega_grid_active": mega_grid_active,
            "polimata_retrains": p_count,
            "last_retrain": p_last
        }
        return status_data
