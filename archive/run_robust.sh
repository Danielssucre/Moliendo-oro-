#!/bin/bash
# Robust Runner for Mac (Prevents Sleep)
echo "🦖 NANOBOT ROBUST LAUNCHER 🛡️"
echo "Preventing System Sleep via 'caffeinate'..."

# Kill previous instances if any (optional, safe to run manually)
pkill -f run_ftmo_manual.py || true

# Activate Venv
source ../.venv/bin/activate

# Run with caffeinate (prevents idle sleep)
# -i: Prevent idle sleep
# -s: Prevent system sleep
caffeinate -i -s python3 scripts/run_ftmo_manual.py --console --risk 0.004
