import json
import os
from datetime import datetime

# Configuration
HISTORY_PATH = "config/health_history.json"
BACKUP_PATH = f"config/health_history_SCRATCH_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
TARGET_SYMBOLS = ["AUDNZD", "BTCUSD", "ETHUSD", "SOLUSD"]

def recover_trades():
    if not os.path.exists(HISTORY_PATH):
        print(f"❌ Error: {HISTORY_PATH} not found.")
        return

    # Load data
    with open(HISTORY_PATH, "r") as f:
        data = json.load(f)

    n1_trades = data.get("neme1_trades", [])
    n2_trades = data.get("neme2_trades", [])

    print(f"📊 Before: NEME1={len(n1_trades)} | NEME2={len(n2_trades)}")

    new_n1 = []
    to_move = []

    for trade in n1_trades:
        symbol = trade.get("symbol", "").upper()
        if symbol in TARGET_SYMBOLS:
            to_move.append(trade)
        else:
            new_n1.append(trade)

    print(f"🔄 Migrating {len(to_move)} trades...")

    # Verification: Total must stay the same
    total_before = len(n1_trades) + len(n2_trades)
    
    # Update lists
    data["neme1_trades"] = new_n1
    data["neme2_trades"] = n2_trades + to_move

    total_after = len(data["neme1_trades"]) + len(data["neme2_trades"])

    if total_before != total_after:
        print(f"❌ Safety check failed: Total trades mismatch ({total_before} vs {total_after})")
        return

    # Save
    with open(HISTORY_PATH, "w") as f:
        json.dump(data, f, indent=4)

    print(f"✅ Success: Moved {len(to_move)} trades.")
    print(f"📊 After: NEME1={len(data['neme1_trades'])} | NEME2={len(data['neme2_trades'])}")

if __name__ == "__main__":
    recover_trades()
