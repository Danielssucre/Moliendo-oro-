import os
import json
import logging
from siliconmetatrader5 import MetaTrader5
from datetime import datetime, timedelta

# Configuración de Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MULTI_ACCOUNT_SYNC")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
HISTORY_PATH = os.path.join(PROJECT_ROOT, "config/health_history.json")

# Lista de cuentas a auditar con sus llaves
ACCOUNTS = [
    {"login": 1513147268, "password": "6CIq!7!x7", "server": "FTMO-Demo"},
    {"login": 1513181406, "password": "$M5K?!weWDi", "server": "FTMO-Demo"},
    {"login": 1513194377, "server": "FTMO-Demo"}
]

def harvest_experience():
    client = MetaTrader5(port=18812)
    master_trades = {} 

    servers = ["FTMO-Demo", "FTMO-Demo2", "FTMO-Server"]
    
    for acc in ACCOUNTS:
        success = False
        for srv in servers:
            logger.info(f"🏦 Probando cuenta {acc['login']} en servidor {srv}...")
            if "password" in acc:
                log_res = client.initialize(login=acc["login"], password=acc["password"], server=srv)
            else:
                log_res = client.initialize(login=acc["login"], server=srv)

            if log_res:
                # Traer historial extenso (1 año)
                from_date = datetime.now() - timedelta(days=365)
                deals = client.history_deals_get(from_date, datetime.now())
                
                if deals and len(deals) > 0:
                    positions = {}
                    for d in deals:
                        if d.symbol == "": continue
                        pid = d.position_id
                        if pid not in positions:
                            positions[pid] = {
                                "ticket": pid,
                                "symbol": d.symbol,
                                "profit": 0,
                                "time": d.time,
                                "comment": d.comment
                            }
                        positions[pid]["profit"] += d.profit + d.commission + d.swap
                        if d.time > positions[pid]["time"]:
                            positions[pid]["time"] = d.time

                    for pid, data in positions.items():
                        # FILTRO FORENSE INTELIGENTE:
                        # Importamos cualquier trade que provenga de la arquitectura HIVE/MEGA/NEME
                        comment = data["comment"].upper()
                        bot_tags = ["MEGA", "HIVE", "NEME", "NEM1", "NEM2", "POLIMATA", "NANOBOT"]
                        
                        is_bot_trade = any(tag in comment for tag in bot_tags)
                        
                        if is_bot_trade:
                            trade = {
                                "ticket": pid,
                                "symbol": data["symbol"],
                                "profit": round(data["profit"], 2),
                                "mae_usd": abs(data["profit"]) * 0.3,
                                "comment": data["comment"],
                                "time": datetime.fromtimestamp(data["time"]).isoformat(),
                                "account": acc["login"],
                                "server": srv
                            }
                            master_trades[pid] = trade
                    
                    logger.info(f"✅ ¡ÉXITO! Recuperados {len(positions)} trades de {acc['login']} en {srv}.")
                    success = True
                    client.shutdown()
                    break # Si funcionó este servidor, pasamos a la siguiente cuenta
                client.shutdown()
        
        if not success:
            logger.error(f"❌ No se pudo recuperar historial para {acc['login']} en ningún servidor.")

    # Guardar base de datos unificada
    history_data = {
        "neme1_trades": [],
        "neme2_trades": list(master_trades.values()),
        "last_sync": datetime.now().isoformat(),
        "total_experience_points": len(master_trades)
    }

    with open(HISTORY_PATH, "w") as f:
        json.dump(history_data, f, indent=4)
    
    logger.info(f"💎 Base de datos UNIFICADA: {len(master_trades)} trades de experiencia acumulada.")

if __name__ == "__main__":
    harvest_experience()
    # Refrescar reporte
    try:
        from src.nanobot.asset_governance import AssetHealthMonitor
        monitor = AssetHealthMonitor()
        monitor.refresh_report()
    except: pass
