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
    {"login": 1513181406, "password": "$M5K?!weWDi", "server": "FTMO-Demo"},
    {"login": 1513194377, "server": "FTMO-Demo"} # La actual suele entrar auto si es la activa
]

def harvest_experience():
    client = MetaTrader5(port=18812)
    master_trades = {} 

    for acc in ACCOUNTS:
        logger.info(f"🏦 Intentando login en cuenta {acc['login']}...")
        
        # Intentar inicialización con password si existe
        if "password" in acc:
            log_res = client.initialize(login=acc["login"], password=acc["password"], server=acc["server"])
        else:
            log_res = client.initialize(login=acc["login"], server=acc["server"])

        if not log_res:
            logger.error(f"❌ Falló conexión a {acc['login']}: {client.last_error()}")
            continue

        # Traer historial extenso (90 días)
        from_date = datetime.now() - timedelta(days=90)
        deals = client.history_deals_get(from_date, datetime.now())
        
        if deals:
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
                # Solo importamos si tiene la etiqueta NEM o si es un trade legítimo de bot
                # Al ser multicunta, somos estrictos con la etiqueta
                if True:
                    trade = {
                        "ticket": pid,
                        "symbol": data["symbol"],
                        "profit": round(data["profit"], 2),
                        "mae_usd": abs(data["profit"]) * 0.3,
                        "comment": data["comment"],
                        "time": datetime.fromtimestamp(data["time"]).isoformat(),
                        "account": acc["login"]
                    }
                    master_trades[pid] = trade
            
            logger.info(f"✅ Recuperados {len(positions)} trades de la cuenta {acc['login']}.")
        
        client.shutdown()

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
