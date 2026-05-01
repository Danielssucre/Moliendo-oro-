import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from src.nanobot.asset_governance import AssetHealthMonitor
import json

monitor = AssetHealthMonitor()
report = monitor.refresh_report()

output_path = os.path.join("config", "asset_health_report.json")
with open(output_path, "w") as f:
    json.dump(report, f, indent=4)

print(f"✅ Health Report manually updated in {output_path}")
for sym, data in report.items():
    if data['health_score'] > 40:
        print(f"  - {sym}: {data['health_score']}% ({data['status']})")
