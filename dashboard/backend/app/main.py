from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.models.schemas import BotConfig, BotStatus, TradeStats
from app.services.bot_manager import BotManager
from app.services.mt5_service import MT5Service
import os
import json
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DASHBOARD_API")

app = FastAPI(title="Quantum Trading Dashboard API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/Users/danielsuarezsucre/TRADING/trading_agent")
mt5_service = MT5Service(PROJECT_ROOT)
bot_manager = BotManager(PROJECT_ROOT, mt5_service=mt5_service)

@app.get("/status", response_model=BotStatus)
async def get_status():
    return bot_manager.get_status()

@app.get("/signals")
async def get_signals():
    # Read last signals from multiple log sources
    signals = []
    log_pattern = re.compile(r"(\d{2}:\d{2}:\d{2}) \| INFO\s+\| 🔍 \[\d/\d\] SIGNAL: (\w+) \| (\w+) \| Str: ([^|]+) \| Src: (\w+)")
    
    import glob
    log_files = glob.glob(os.path.join(PROJECT_ROOT, "logs/trading_*.log"))
    dash_log = os.path.join(PROJECT_ROOT, "logs/dashboard_bot.log")
    if os.path.exists(dash_log):
        log_files.append(dash_log)
        
    if not log_files:
        return []
    
    # Sort logs by modification time and pick top 2
    log_files.sort(key=os.path.getmtime, reverse=True)
    recent_logs = log_files[:2]
    
    seen_sigs = set()
    for log_path in recent_logs:
        try:
            with open(log_path, "r") as f:
                # Scan last 2000 lines
                lines = f.readlines()[-2000:]
                for line in lines:
                    match = log_pattern.search(line)
                    if match:
                        data = {
                            "time": match.group(1),
                            "symbol": match.group(2),
                            "type": match.group(3),
                            "strategy": match.group(4).strip(),
                            "source": match.group(5)
                        }
                        sig_key = f"{data['time']}_{data['symbol']}_{data['type']}"
                        if sig_key not in seen_sigs:
                            signals.append(data)
                            seen_sigs.add(sig_key)
        except:
            pass
            
    # Sort all found signals by time descending
    signals.sort(key=lambda x: x["time"], reverse=True)
    return signals[:50]

@app.post("/config", response_model=BotConfig)
async def update_config(config: BotConfig):
    config_path = os.path.join(os.getcwd(), "../../config/trading_config.json")
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            full_config = json.load(f)
        
        # Update top-level flags
        full_config["risk_management"]["risk_per_trade"] = config.risk_per_trade
        full_config["mega_grid_enabled"] = config.terra_mode
        
        with open(config_path, 'w') as f:
            json.dump(full_config, f, indent=4)
            
    return config

@app.post("/config/mega-grid")
async def toggle_mega_grid(enabled: bool):
    config_path = os.path.join(os.getcwd(), "../../config/trading_config.json")
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            full_config = json.load(f)
        
        full_config["mega_grid_enabled"] = enabled
        
        with open(config_path, 'w') as f:
            json.dump(full_config, f, indent=4)
            
    return {"status": "success", "mega_grid_enabled": enabled}

@app.post("/start")
async def start_bot(config: BotConfig):
    # Update credentials if provided
    if config.mt5:
        creds_path = os.path.join(PROJECT_ROOT, "config/credentials.json")
        os.makedirs(os.path.dirname(creds_path), exist_ok=True)
        with open(creds_path, 'w') as f:
            json.dump({"mt5": config.mt5.dict()}, f, indent=4)
        
    # AUTOMATIC MT5 CONNECTION BEFORE BOT START
    logger.info("Auto-connecting MT5 before bot startup...")
    mt5_service.connect()
    
    # Start bot
    result = bot_manager.start_bot(capital=100000) # Default capital or from config
    return result

@app.post("/stop")
async def stop_bot():
    return bot_manager.stop_bot()

@app.get("/accounts")
async def get_accounts():
    accounts = mt5_service.list_discovered_accounts()
    # Add labels for convenience
    for acc in accounts:
        acc["label"] = f"{acc['server']} - {acc['account']}"
    return accounts

@app.post("/accounts/select")
async def select_account(acc_data: dict):
    # acc_data: {"account": 1234, "server": "Server-Name", "password": "..."}
    account = acc_data.get("account")
    server = acc_data.get("server")
    password = acc_data.get("password")
    
    if not account or not server:
        raise HTTPException(status_code=400, detail="Account and Server required")
        
    # Update credentials file
    creds_path = os.path.join(PROJECT_ROOT, "config/credentials.json")
    with open(creds_path, 'w') as f:
        json.dump({
            "mt5": {
                "account": int(account),
                "server": server,
                "password": password or "" # Might be empty if already saved in MT5
            }
        }, f, indent=4)
    
    # Stop current bot if running
    bot_manager.stop_bot()
    
    # Reconnect MT5 with new credentials
    mt5_service.connect()
    
    return {"status": "success", "message": f"Switched to {account} on {server}"}

@app.get("/config", response_model=BotConfig)
async def get_config():
    config_path = os.path.join(PROJECT_ROOT, "config/trading_config.json")
    creds_path = os.path.join(PROJECT_ROOT, "config/credentials.json")
    
    risk = 0.004
    mega_grid = True
    mt5_creds = None
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                cfg = json.load(f)
                risk = cfg.get("risk_management", {}).get("risk_per_trade", 0.004)
                mega_grid = cfg.get("mega_grid_enabled", True)
        except: pass
        
    if os.path.exists(creds_path):
        try:
            with open(creds_path, 'r') as f:
                data = json.load(f)
                mt5_creds = data.get("mt5")
        except: pass
        
    return BotConfig(
        risk_per_trade=risk,
        terra_mode=mega_grid,
        mt5=mt5_creds
    )

@app.get("/stats", response_model=TradeStats)
async def get_stats():
    from datetime import datetime, timedelta, timezone
    import glob
    
    # 1. Real MT5 Data via MT5Service
    mt5_stats = mt5_service.get_account_stats()
    
    if mt5_stats:
        equity = mt5_stats["equity"]
        balance = mt5_stats["balance"]
        margin = mt5_stats["margin"]
        free_margin = mt5_stats["free_margin"]
        margin_level = mt5_stats["margin_level"]
        daily_pnl = mt5_stats["daily_pnl"]
        active_trades = mt5_stats["active_trades"]
        
        # Total PnL from history
        from datetime import datetime, timedelta
        start_time = datetime.now() - timedelta(days=365*3)
        all_deals = mt5_service.client.history_deals_get(start_time, datetime.now())
        total_historical_profit = sum(d.profit for d in all_deals) if all_deals else 0.0
        total_pnl = mt5_stats["floating_profit"] + total_historical_profit
    else:
        # Fallback
        equity = 200000.00
        balance = 200000.00
        margin = 0.0
        free_margin = 0.0
        margin_level = 0.0
        daily_pnl = 0.0
        active_trades = 0
        total_pnl = 0.0
    
    # ... rest same ...
    model_files = glob.glob(os.path.join(PROJECT_ROOT, "models/*.zip"))
    polimata_retrains = len(model_files)

    # Determine Risk Label / Micro-Sizing Logic
    is_micro_sizing = False
    
    # Load custom risk from config
    try:
        config_path = os.path.join(PROJECT_ROOT, "config/trading_config.json")
        with open(config_path, 'r') as f:
            t_config = json.load(f)
            risk = t_config.get("risk_per_trade", 0.004)
    except:
        risk = 0.004
        
    risk_label = f"{risk * 100:.2f}%"
    
    if balance < 500:
        is_micro_sizing = True
        if balance < 100:
            risk_label = "SURVIVAL MODE (0.01 Lots)"
        else:
            lots = (int(balance / 100)) * 0.01
            risk_label = f"GROWTH MODE ({lots:.2f} Lots)"
    else:
        # Fetch from config logic
        risk_label = f"{risk * 100:.2f}%"

    return {
        "daily_pnl": daily_pnl,
        "total_pnl": total_pnl,
        "equity": equity,
        "balance": balance,
        "active_trades": active_trades,
        "polimata_retrains": polimata_retrains,
        "margin": margin,
        "free_margin": free_margin,
        "margin_level": margin_level,
        "is_micro_sizing": is_micro_sizing,
        "risk_label": risk_label
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
