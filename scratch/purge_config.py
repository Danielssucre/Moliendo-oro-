import os
import sys
import json
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from nanobot.statistical_health_monitor import StatisticalHealthMonitor

def purge_legacy_keys():
    # Instantiate monitor
    config_path = "config/statistical_config.json"
    monitor = StatisticalHealthMonitor(config_path=config_path)
    
    print(f"🔍 Current auto_pilot keys: {list(monitor.auto_pilot.keys())}")
    
    # Trigger the new Purge-and-Merge save logic
    monitor.save_config()
    
    # Verify
    with open(config_path, "r") as f:
        final_cfg = json.load(f)
    
    print(f"✅ Final auto_pilot keys: {list(final_cfg.get('auto_pilot', {}).keys())}")
    
    has_legacy = any(len(k) > 6 and ("USD" in k or "USDT" in k) for k in final_cfg.get("auto_pilot", {}))
    if has_legacy:
        print("❌ FAILED: Legacy keys still present!")
    else:
        print("🎉 SUCCESS: All legacy keys purged.")

if __name__ == "__main__":
    purge_legacy_keys()
