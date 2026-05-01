import os
import csv
import json
from datetime import datetime

HEART_FILE = "/Users/danielsuarezsucre/TRADING/trading_agent/config/health_history.json"
LOG_DIR = "/Users/danielsuarezsucre/TRADING/trading_agent/logs/history"

def collect_treasures():
    if not os.path.exists(HEART_FILE):
        data = {"neme1_trades": [], "neme2_trades": []}
    else:
        with open(HEART_FILE, 'r') as f:
            data = json.load(f)
            
    # Tickets ya existentes para evitar duplicados
    existing_tickets = set()
    for t in data.get("neme1_trades", []) + data.get("neme2_trades", []):
        existing_tickets.add(t["ticket"])
    
    total_added = 0
    
    if not os.path.exists(LOG_DIR):
        print(f"❌ Directorio de logs no encontrado: {LOG_DIR}")
        return

    # Escanear CSVs
    for filename in os.listdir(LOG_DIR):
        if filename.startswith("trades_") and filename.endswith(".csv"):
            filepath = os.path.join(LOG_DIR, filename)
            with open(filepath, 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) < 12: continue
                    
                    # Estructura típica: Time, Ticket, Symbol, Type, Lot, Price, SL, TP, Commission, Swap, Profit, Comment
                    time_str, ticket, symbol, _, _, _, _, _, comm, swap, profit, comment = row[:12]
                    
                    try:
                        ticket = int(ticket)
                        profit = float(profit) + float(comm) + float(swap)
                    except: continue
                    
                    if ticket in existing_tickets: continue
                    
                    comment_up = comment.upper()
                    bot_tags = ["MEGA", "HIVE", "NEME", "NEM1", "NEM2", "POLIMATA", "NANOBOT"]
                    
                    if any(tag in comment_up for tag in bot_tags):
                        trade = {
                            "ticket": ticket,
                            "symbol": symbol,
                            "profit": round(profit, 2),
                            "mae_usd": abs(profit) * 0.3, # Estimación conservadora
                            "comment": comment,
                            "time": time_str.replace(" ", "T"),
                            "account": "LEGACY_RECOVERY",
                            "server": "LOCAL_LOGS"
                        }
                        
                        # Por ahora los mandamos a neme2 que es el motor activo
                        if "neme2_trades" not in data: data["neme2_trades"] = []
                        data["neme2_trades"].append(trade)
                        existing_tickets.add(ticket)
                        total_added += 1
                        
    with open(HEART_FILE, 'w') as f:
        json.dump(data, f, indent=4)
        
    print(f"✅ ¡TESOROS RECUPERADOS! Se han inyectado {total_added} trades históricos en la base de datos.")

if __name__ == "__main__":
    collect_treasures()
