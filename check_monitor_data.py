import sys, os
import json
# Load statistical_config.json
path = "/Users/danielsuarezsucre/TRADING/trading_agent/config/statistical_config.json"
if os.path.exists(path):
    with open(path, "r") as f:
        data = json.load(f)
        print("Statistical Config Data:")
        # print keys except maybe long lists
        for k in data:
            if isinstance(data[k], list):
                print(f"  {k}: list length {len(data[k])}")
            else:
                print(f"  {k}: {data[k]}")
else:
    print("Config file not found")

# Check governance.json
gov_path = "/Users/danielsuarezsucre/TRADING/trading_agent/config/governance.json"
if os.path.exists(gov_path):
    with open(gov_path, "r") as f:
        gov = json.load(f)
        print("\nGovernance Data:")
        print(json.dumps(gov, indent=2))
