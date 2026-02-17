#!/bin/bash
# NANOBOT LIVE TRADING LAUNCHER 🚀
# Usage: ./run_live_trading.sh [CAPITAL]

CAPITAL=${1:-10000}

echo "🦖 ACTIVATING NANOBOT ECOSYSTEM..."
echo "-------------------------------------------"

# ENV VARS
export PYTHONPATH=$PYTHONPATH:$(pwd)
export GEMINI_API_KEY="AIzaSyA8Fja6nXeuXGpkJHlbk9w56MVq661QBR0"
# 1. Check/Start MetaTrader 5 (Port 8001)
if lsof -i :8001 > /dev/null
then
    echo "✅ MetaTrader 5 is responding (Port 8001)."
else
    echo "⚠️ MT5 Port 8001 closed. Launching..."
    open -a "MetaTrader 5"
    echo "⏳ Waiting 30s for MT5 to initialize..."
    sleep 30
fi

# 2. Activate Python Environment
source ../.venv/bin/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Error: Virtual Environment not found!"
    exit 1
fi

# 3. Start Watchdog (Background)
echo "🛡️ Starting Watchdog..."
python3 scripts/ftmo_watchdog.py &
WATCHDOG_PID=$!

# 4. Start Trading Core
echo "🧠 Starting HIVE V5 Core (Capital: \$$CAPITAL)..."
echo "📘 Manual Operativo: brain/manual_operativo_bot.md"
python3 -u scripts/run_ftmo_manual.py --capital $CAPITAL

# Cleanup
kill $WATCHDOG_PID
