from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json
import os
import uvicorn
import logging
import sys

# --- CONFIGURACIÓN DE RUTAS ABSOLUTAS ---
# Determinamos la raíz del proyecto de forma dinámica pero absoluta
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__)) # src/scripts
BASE_DIR = os.path.dirname(os.path.dirname(CURRENT_DIR)) # Raíz del proyecto

# [v6.7.0] Inyección de Ruta para Módulos Internos (Apunta a SRC)
sys.path.append(os.path.join(BASE_DIR, "src"))
BRIDGE_PATH = os.path.join(BASE_DIR, "config", "dashboard_bridge.json")
LOG_PATH = os.path.join(BASE_DIR, "logs", "run_live_dashboard.log")
AFFINITY_PATH = os.path.join(BASE_DIR, "data", "research", "affinity_map.json")
PERSISTENCE_PATH = os.path.join(BASE_DIR, "config", "state_persistence.json")

# Configuración de Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QuantumBridge")

app = FastAPI(title="Quantum OMEGA+ Command Bridge")

@app.get("/system-status")
def get_system_status():
    """Retorna el estado de confianza y bloqueos del sistema."""
    try:
        from nanobot.utils.database import SecureDatabaseManager as db
        state = db.load_json(PERSISTENCE_PATH, default={})
        
        tier = state.get("trust_tier", 1)
        tier_map = {1: 0.25, 2: 0.50, 3: 0.75, 4: 1.00}
        
        return {
            "trust_tier": tier,
            "lock_pct": tier_map.get(tier, 0.25),
            "daily_start": state.get("daily_start_balance", 0.0),
            "consecutive_wins": state.get("consecutive_baskets", 0)
        }
    except Exception as e:
        return {"error": str(e), "lock_pct": 0.25}

# --- MIDDLEWARE DE CORS ATÓMICO ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permitir acceso desde file:// y otros orígenes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/affinity")
def get_affinity():
    """Retorna el mapa de afinidad para el Heatmap del Dashboard de forma segura."""
    try:
        if not os.path.exists(AFFINITY_PATH):
            return {}
        with open(AFFINITY_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error en lectura segura de afinidad: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class SymbolConfig(BaseModel):
    status: str
    strategy_mode: str
    manual_nem_role: Optional[str] = None
    max_levels_override: int
    emergency_stop: bool

@app.on_event("startup")
async def startup_event():
    logger.info("📡 QUANTUM BRIDGE INICIADO (Modo Soberano)")
    logger.info(f"📍 BASE_DIR: {BASE_DIR}")
    logger.info(f"📂 BRIDGE_PATH: {BRIDGE_PATH}")
    
    # Asegurar que el directorio de config existe
    os.makedirs(os.path.dirname(BRIDGE_PATH), exist_ok=True)
    
    if not os.path.exists(BRIDGE_PATH):
        logger.warning("⚠️ Bridge JSON no encontrado. Inicializando vacío...")
        with open(BRIDGE_PATH, "w") as f:
            json.dump({}, f)

@app.get("/config")
def get_config():
    try:
        if not os.path.exists(BRIDGE_PATH):
            return {}
        with open(BRIDGE_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error en lectura de config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update/{symbol}")
def update_symbol(symbol: str, config: SymbolConfig):
    try:
        with open(BRIDGE_PATH, "r") as f:
            data = json.load(f)
        
        data[symbol] = config.dict()
        
        with open(BRIDGE_PATH, "w") as f:
            json.dump(data, f, indent=4)
        
        logger.info(f"🎯 COMANDO TÁCTICO: {symbol} configurado como {config.status}")
        return {"status": "success", "symbol": symbol}
    except Exception as e:
        logger.error(f"Error en actualización de {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/atomic-purge")
def atomic_purge():
    try:
        if not os.path.exists(BRIDGE_PATH): return {"status": "no_file"}
        with open(BRIDGE_PATH, "r") as f:
            data = json.load(f)
        
        for s in data:
            data[s]["status"] = "OFF"
            data[s]["emergency_stop"] = True
            
        with open(BRIDGE_PATH, "w") as f:
            json.dump(data, f, indent=4)
        
        logger.warning("🌊 ATOMIC PURGE: FLOTA LIQUIDADA")
        return {"status": "purged", "count": len(data)}
    except Exception as e:
        logger.error(f"Error en Purga Atómica: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/logs")
def get_recent_logs():
    try:
        if not os.path.exists(LOG_PATH):
            return {"logs": ["Esperando primer latido del bot..."]}
        with open(LOG_PATH, "r") as f:
            lines = f.readlines()
            return {"logs": lines[-60:]} # Enviamos 60 líneas para mayor contexto
    except Exception as e:
        return {"logs": [f"Error accediendo a logs: {str(e)}"]}

if __name__ == "__main__":
    # Forzar ejecución en el puerto 8080 en localhost
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")
