import json
import os

# Configuration
HISTORY_PATH = "config/health_history.json"
# Target symbols (short names) that should be in NEMESIS_2 based on user request
TARGET_RECOVERY = ["AUDNZD", "BTC", "ETH", "SOL"]

def normalize_symbol(symbol):
    """Normalization logic from statistical_health_monitor.py"""
    if not symbol:
        return "DEFAULT"
    s = symbol.upper()
    for suffix in ["USDT", "USD", "-USD", "/USD", ".P"]:
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    return s

def universal_sync():
    if not os.path.exists(HISTORY_PATH):
        print(f"❌ Error: {HISTORY_PATH} not found.")
        return

    with open(HISTORY_PATH, "r") as f:
        data = json.load(f)

    n1_trades = data.get("neme1_trades", [])
    n2_trades = data.get("neme2_trades", [])

    print(f"📊 Initial: NEME1={len(n1_trades)} | NEME2={len(n2_trades)}")

    # Step 1: Normalize ALL symbols in NEME1 and NEME2
    for t in n1_trades:
        t["symbol"] = normalize_symbol(t.get("symbol"))
    
    for t in n2_trades:
        t["symbol"] = normalize_symbol(t.get("symbol"))

    # Step 2: Migrate target recovery trades from NEME1 to NEME2
    # Ensure they are currently in NEME1 (some might have been moved incorrectly before)
    new_n1 = []
    to_move = []

    for t in n1_trades:
        norm_s = t["symbol"]
        if norm_s in TARGET_RECOVERY:
            to_move.append(t)
        else:
            new_n1.append(t)

    print(f"🔄 Normalization complete. Migrating {len(to_move)} recovered trades...")

    # Verification
    total_before = len(n1_trades) + len(n2_trades)
    data["neme1_trades"] = new_n1
    data["neme2_trades"] = n2_trades + to_move
    total_after = len(data["neme1_trades"]) + len(data["neme2_trades"])

    if total_before != total_after:
        print(f"❌ Critical failure: Total count mismatch!")
        return

    # Save
    with open(HISTORY_PATH, "w") as f:
        json.dump(data, f, indent=4)

    print(f"✅ Success: Moved {len(to_move)} trades and normalized all records.")
    print(f"📊 Final: NEME1={len(data['neme1_trades'])} | NEME2={len(data['neme2_trades'])}")

if __name__ == "__main__":
    universal_sync()
