import pandas as pd
import numpy as np
import json
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger("LHN_TRAINER")

def train_megagrid():
    logger.info("🧠 [LHN-MEGA] Iniciando entrenamiento Meta-RL con historial de la cuenta quemada...")
    
    file_path = "data/research/recovered_lhn_burned_account.csv"
    if not os.path.exists(file_path):
        logger.error("No se encontró el archivo de datos recuperados.")
        return
        
    df = pd.read_csv(file_path)
    
    blocks = {"ALFA": [], "EXPL": [], "NEME": []}
    for _, row in df.iterrows():
        comment = str(row['config'])
        if "ALFA" in comment: blocks["ALFA"].append(row['profit'])
        elif "EXPL" in comment: blocks["EXPL"].append(row['profit'])
        elif "NEME" in comment: blocks["NEME"].append(row['profit'])
        
    alfa_pnl = sum(blocks["ALFA"])
    expl_pnl = sum(blocks["EXPL"])
    neme_pnl = sum(blocks["NEME"])
    
    logger.info(f"📊 Resultados asimilados - ALFA: ${alfa_pnl:.2f} | EXPL: ${expl_pnl:.2f} | NEME: ${neme_pnl:.2f}")
    
    # Simple reinforcement logic: if Nemesis is the only profitable, we increase its weight in future probabilistic decisions
    total_trades = len(df)
    win_rates = {}
    for b in blocks:
        if len(blocks[b]) > 0:
            wins = sum(1 for p in blocks[b] if p > 0)
            win_rates[b] = wins / len(blocks[b])
        else:
            win_rates[b] = 0.0
            
    logger.info(f"🎯 Tasas de acierto (Win Rate) - ALFA: {win_rates['ALFA']:.1%} | EXPL: {win_rates['EXPL']:.1%} | NEME: {win_rates['NEME']:.1%}")
    
    # Save optimized weights
    weights = {
        "ALFA": 0.50, # Keep distribution matching the 50/25/25 split for allocation
        "EXPL": 0.25, 
        "NEME": 0.25,
        "risk_modifiers": { # But modify the risk appetite dynamically
            "ALFA": round(max(0.2, 1.0 + (alfa_pnl / 1000)), 2),
            "EXPL": round(max(0.2, 1.0 + (expl_pnl / 1000)), 2),
            "NEME": round(min(2.0, 1.0 + (neme_pnl / 100)), 2)
        },
        "version": "LHN_BETA_V2_BURNED_LEARNING",
        "description": "Pesos ajustados tras asimilar la quema de cuenta. NEME reforzado."
    }
    
    os.makedirs("models/lhn_weights", exist_ok=True)
    with open("models/lhn_weights/mega_grid_v2.json", "w") as f:
        json.dump(weights, f, indent=4)
        
    logger.info("✅ Entrenamiento completado. Nuevos pesos de riesgo guardados en models/lhn_weights/mega_grid_v2.json")

if __name__ == "__main__":
    train_megagrid()
