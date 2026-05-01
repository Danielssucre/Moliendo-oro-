import pandas as pd
import json
import os
from datetime import datetime

CSV_FILE = "/Users/danielsuarezsucre/TRADING/trading_agent/data/research/shadow_grid_results.csv"
HEART_FILE = "/Users/danielsuarezsucre/TRADING/trading_agent/config/health_history.json"

def fusion_total():
    if not os.path.exists(CSV_FILE):
        print("❌ CSV de sombras no encontrado.")
        return

    df = pd.read_csv(CSV_FILE)
    print(f"📁 Cargadas {len(df)} filas de historia en la sombra.")

    if not os.path.exists(HEART_FILE):
        data = {"neme1_trades": [], "neme2_trades": []}
    else:
        with open(HEART_FILE, 'r') as f:
            data = json.load(f)

    existing_tickets = set()
    for t in data.get("neme1_trades", []) + data.get("neme2_trades", []):
        existing_tickets.add(t["ticket"])

    added = 0
    for _, row in df.iterrows():
        ticket = int(row['ticket'])
        if ticket in existing_tickets:
            continue
        
        # Clasificamos por comentario o tag
        config = str(row['config']).upper()
        
        # Outcome R de 1.0 suele ser un Win, -1.0 un Loss
        # Estimamos un profit nominal para que el motor de GHI funcione
        outcome_r = float(row['outcome_r'])
        estimated_profit = outcome_r * 20.0 # Un profit 'base' de $20 por R
        
        trade = {
            "ticket": ticket,
            "symbol": row['symbol'],
            "profit": round(estimated_profit, 2),
            "mae_usd": abs(float(row['mae_r'])) * 10.0,
            "comment": row['config'],
            "time": row['time'],
            "account": "SHADOW_RECOVERY",
            "server": "RESEARCH_DATA"
        }

        # Determinamos a qué sistema pertenece
        if "NEME" in config or "ANTITHESIS" in config:
            if "neme2_trades" not in data: data["neme2_trades"] = []
            data["neme2_trades"].append(trade)
            added += 1
        elif "ALFA" in config or "FIXED" in config or "HIVE" in config:
            if "neme1_trades" not in data: data["neme1_trades"] = []
            data["neme1_trades"].append(trade)
            added += 1
        
        existing_tickets.add(ticket)

    with open(HEART_FILE, 'w') as f:
        json.dump(data, f, indent=4)

    print(f"✅ FUSIÓN COMPLETADA: Se han inyectado {added} trades de la historia profunda.")

if __name__ == "__main__":
    fusion_total()
