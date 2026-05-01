import json
import os

config_path = "/Users/danielsuarezsucre/TRADING/trading_agent/config/statistical_config.json"
gov_path = "/Users/danielsuarezsucre/TRADING/trading_agent/config/governance.json"

if os.path.exists(config_path):
    with open(config_path, "r") as f:
        config = json.load(f)
    
    gov_data = {
        "preferences": config.get("preferences", {}),
        "auto_pilot": config.get("auto_pilot", {}),
        "last_updated": "2026-04-19T20:00:00Z"
    }
    
    with open(gov_path, "w") as f:
        json.dump(gov_data, f, indent=4)
    print(f"✅ Migrated governance to {gov_path}")
else:
    print("❌ Config not found")
