import json
import os

def init_dashboard_bridge():
    # Definición de activos institucionales (Default del Bot)
    assets = [
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD",
        "GBPJPY", "EURJPY", "EURGBP", "AUDJPY", "CHFJPY", "CADJPY",
        "EURAUD", "GBPAUD", "EURNZD", "NZDJPY",
        "XAUUSD", "XAGUSD", "WTI",
        "NAS100", "SPX500", "DAX40", "US30",
        "BTCUSD", "ETHUSD", "SOLUSD"
    ]
    
    bridge_config = {}
    for symbol in assets:
        bridge_config[symbol] = {
            "status": "ON",
            "strategy_mode": "AUTO",
            "manual_nem_role": None,
            "max_levels_override": 7,
            "emergency_stop": False
        }
    
    # Path absoluto basado en la raíz del proyecto
    base_dir = "/Users/danielsuarezsucre/TRADING/trading_agent"
    config_dir = os.path.join(base_dir, "config")
    
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
        
    config_path = os.path.join(config_dir, "dashboard_bridge.json")
    
    with open(config_path, "w") as f:
        json.dump(bridge_config, f, indent=4)
        
    print(f"✅ PUENTE DE PERSISTENCIA INICIALIZADO: {config_path}")
    print(f"📊 {len(assets)} Activos vinculados a la Matrix.")

if __name__ == "__main__":
    init_dashboard_bridge()
