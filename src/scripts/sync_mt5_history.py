import os
import json
import logging
from siliconmetatrader5 import MetaTrader5
from datetime import datetime, timedelta

# Configuración de Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SYNC_MT5_HISTORY")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
HISTORY_PATH = os.path.join(PROJECT_ROOT, "config/health_history.json")

def sync_with_real_account():
    client = MetaTrader5(port=18812)
    # Credenciales FTMO Demo desde tu config
    c_login = 1513194377
    c_server = "FTMO-Demo"
    
    if not client.initialize(login=c_login, server=c_server):
        logger.error(f"❌ Error al conectar con MT5: {client.last_error()}")
        return

    # Traer historial de los últimos 90 días para asegurar base estadística
    from_date = datetime.now() - timedelta(days=90)
    logger.info(f"📥 Descargando historial desde {from_date}...")
    
    # deals_get trae los registros de ejecución. Agruparemos por position_id para tener "Trades" reales.
    deals = client.history_deals_get(from_date, datetime.now())
    
    if deals is None:
        logger.warning("⚠️ No se encontraron deals en el historial.")
        client.shutdown()
        return

    # Agrupar por posición
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
        # Actualizar tiempo al más reciente para saber cuándo cerró
        if d.time > positions[pid]["time"]:
            positions[pid]["time"] = d.time

    logger.info(f"✅ Se han recuperado {len(positions)} posiciones (trades) de la cuenta.")

    structured_trades = []
    for pid, data in positions.items():
        trade = {
            "ticket": pid,
            "symbol": data["symbol"],
            "profit": round(data["profit"], 2),
            "mae_usd": abs(data["profit"]) * 0.3, # Estimación MAE conservadora
            "comment": data["comment"],
            "time": datetime.fromtimestamp(data["time"]).isoformat()
        }
        structured_trades.append(trade)

    # Actualizar health_history.json
    # Los trataremos como "neme2_trades" por defecto para que el auditor los procese
    history_data = {
        "neme1_trades": [],
        "neme2_trades": structured_trades,
        "last_sync": datetime.now().isoformat(),
        "account_id": c_login
    }

    with open(HISTORY_PATH, "w") as f:
        json.dump(history_data, f, indent=4)
    
    logger.info(f"💾 Historial actualizado con {len(structured_trades)} trades reales de la cuenta.")
    client.shutdown()

if __name__ == "__main__":
    sync_with_real_account()
    
    # Forzar actualización del reporte de gobernanza
    from src.nanobot.asset_governance import AssetHealthMonitor
    monitor = AssetHealthMonitor()
    monitor.refresh_report()
    logger.info("📊 Reporte de Gobernanza actualizado con datos de la cuenta real.")
