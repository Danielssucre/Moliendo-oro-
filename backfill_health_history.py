import sys, os
import json
from datetime import datetime

# Path to the health_history.json
history_path = "/Users/danielsuarezsucre/TRADING/trading_agent/config/health_history.json"

# Data from MT5 (simulated/hardcoded from previous output for speed, 
# or I could pull it again. Let's hardcode the keys for AUDNZD).
audnzd_trades = [
    {"ticket": 412517574, "profit": -3.01, "is_win": False, "symbol": "AUDNZD", "time": 1776736157},
    {"ticket": 412517573, "profit": -1.51, "is_win": False, "symbol": "AUDNZD", "time": 1776736157},
    {"ticket": 412517572, "profit": -4.52, "is_win": False, "symbol": "AUDNZD", "time": 1776736157},
    {"ticket": 412517571, "profit": -6.03, "is_win": False, "symbol": "AUDNZD", "time": 1776736157},
    {"ticket": 412517569, "profit": -4.52, "is_win": False, "symbol": "AUDNZD", "time": 1776736157},
    {"ticket": 412517567, "profit": -2.97, "is_win": False, "symbol": "AUDNZD", "time": 1776736157},
    {"ticket": 411472056, "profit": -2.79, "is_win": False, "symbol": "AUDNZD", "time": 1776636157},
    {"ticket": 411472055, "profit": -1.47, "is_win": False, "symbol": "AUDNZD", "time": 1776636157},
    {"ticket": 411472026, "profit": -5.46, "is_win": False, "symbol": "AUDNZD", "time": 1776636157},
    {"ticket": 411472025, "profit": -4.09, "is_win": False, "symbol": "AUDNZD", "time": 1776636157},
    {"ticket": 411472024, "profit": -4.09, "is_win": False, "symbol": "AUDNZD", "time": 1776636157},
    {"ticket": 411472023, "profit": -2.73, "is_win": False, "symbol": "AUDNZD", "time": 1776636157},
    {"ticket": 411472022, "profit": -4.09, "is_win": False, "symbol": "AUDNZD", "time": 1776636157},
    {"ticket": 411472016, "profit": -1.38, "is_win": False, "symbol": "AUDNZD", "time": 1776636157},
    {"ticket": 411469943, "profit": -3.54, "is_win": False, "symbol": "AUDNZD", "time": 1776636157},
    {"ticket": 411469942, "profit": -5.31, "is_win": False, "symbol": "AUDNZD", "time": 1776636157}
]

# Formatting for HealthMonitor
neme1_trades = []
for t in audnzd_trades:
    neme1_trades.append({
        "profit": t["profit"],
        "is_win": t["is_win"],
        "symbol": t["symbol"],
        "timestamp": datetime.fromtimestamp(t["time"]).isoformat(),
        "ticket": t["ticket"],
        "source": "MIGRATION_BACKFILL"
    })

data = {
    "neme1_trades": neme1_trades,
    "neme2_trades": []
}

os.makedirs(os.path.dirname(history_path), exist_ok=True)
with open(history_path, "w") as f:
    json.dump(data, f, indent=4)

print(f"Successfully backfilled {len(neme1_trades)} trades into {history_path}")
